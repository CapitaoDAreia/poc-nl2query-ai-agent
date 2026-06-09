import os
import sys
from typing import TypedDict, List
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START

from prompts.prompts import FILTER_GENERATION_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from tools.gcp_logging_query import execute_gcp_logging_query

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

load_dotenv()

class AgentState(TypedDict):
    question: str
    retrieved_docs: List[Document]
    gcp_filter_query: str
    gcp_logs_result: List[dict]
    error_message: str
    retry_count: int
    final_response: str


class HermesGraphBuilder:
    def __init__(self, vector_store_manager):
        self.vector_store = vector_store_manager
        
        self.llm = ChatOllama(
            model=os.getenv("LLM_MODEL"),
            temperature=0.1,
            base_url=os.getenv("OLLAMA_HOST")
        )
        
        self.graph = self._build_workflow()

    def _retrieve_context(self, state: AgentState) -> dict:
        print("\nFetching project info using RAG...")
        initial_results = self.vector_store.search(state["question"], k=2)
        
        docs = [doc for doc, score in initial_results] if initial_results else []  

        return {"retrieved_docs": docs}

    def _generate_filter(self, state: AgentState) -> dict:
            print("Building GCP filter string...")
            
            if not state["retrieved_docs"]:
                return {"gcp_filter_query": "", "error_message": "Nenhum contexto técnico encontrado no RAG."}
                
            doc = state["retrieved_docs"][0]
            gcp_service = doc.metadata.get("gcp_service", "unknown")
            path = doc.metadata.get("path", "")
            
            error_context = ""
            if state.get("error_message"):
                error_context = f"\n⚠️ ATENÇÃO: Seu filtro anterior falhou com o erro: {state['error_message']}. Corrija a sintaxe imediatamente."

            prompt_consolidado = FILTER_GENERATION_PROMPT.format(
                gcp_service=gcp_service,
                path=path,
                question=state["question"],
                error_context=error_context
            )

            messages = [HumanMessage(content=prompt_consolidado)]
            filter_string = ""
            
            try:
                response = self.llm.invoke(messages)
                filter_string = response.content.strip().replace("`", "").replace("\n", " ")
            except Exception as e:
                print(f"⚠️ Error calling LLM: {e}")
                
            return {"gcp_filter_query": filter_string}

    def _execute_gcp_query(self, state: AgentState) -> dict:
            print("[Node -> execute_gcp_query] Buscando dados no Cloud Logging...")
            
            logs, error_msg = execute_gcp_logging_query(state["gcp_filter_query"])
            
            return {
                "gcp_logs_result": logs, 
                "error_message": error_msg
            }

    def _synthesize_response(self, state: AgentState) -> dict:
            print("[Node -> synthesize_response] Sintetizando resposta final para o negócio...")
            
            user_message = f"User Question: {state['question']}\n\nGCP Logs Output:\n{str(state['gcp_logs_result'])}"
            
            messages = [
                SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
                HumanMessage(content=user_message)
            ]
            
            response = self.llm.invoke(messages)
            return {"final_response": response.content}

    def _route_after_query(self, state: AgentState) -> str:
        if state.get("error_message") and state.get("retry_count", 0) < 2:
            print(f"🔄 [Routing] Sintaxe inválida detectada. Ativando Reflexion (Tentativa {state['retry_count'] + 1}/2)...")
            return "reflexion_node"
        return "synthesize_node"

    def _reflexion(self, state: AgentState) -> dict:
        return {"retry_count": state["retry_count"] + 1}

    def _build_workflow(self):
        workflow = StateGraph(AgentState)
        
        workflow.add_node("retrieve_node", self._retrieve_context)
        workflow.add_node("generate_filter_node", self._generate_filter)
        workflow.add_node("execute_query_node", self._execute_gcp_query)
        workflow.add_node("reflexion_node", self._reflexion)
        workflow.add_node("synthesize_node", self._synthesize_response)
        
        workflow.add_edge(START, "retrieve_node")
        workflow.add_edge("retrieve_node", "generate_filter_node")
        workflow.add_edge("generate_filter_node", "execute_query_node")
        
        workflow.add_conditional_edges(
            "execute_query_node",
            self._route_after_query,
            {
                "reflexion_node": "reflexion_node",
                "synthesize_node": "synthesize_node"
            }
        )
        
        workflow.add_edge("reflexion_node", "generate_filter_node")
        workflow.add_edge("synthesize_node", END)
        
        return workflow.compile()