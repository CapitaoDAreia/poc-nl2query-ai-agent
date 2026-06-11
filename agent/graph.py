# agent/graph.py
import os
import sys
from typing import TypedDict, List
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START

from agent.prompts.prompts import FILTER_GENERATION_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from agent.tools.gcp_logging_query import execute_gcp_logging_query

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

load_dotenv()

class AgentState(TypedDict):
    question: str
    retrieved_docs: List[Document]
    rag_score: float
    gcp_filter_query: str
    gcp_logs_result: List[dict]
    error_message: str
    retry_count: int
    reasoning_steps: List[str]
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
        steps = state.get("reasoning_steps", []) or []
        steps.append("Iniciando busca semântica no banco vetorial via RAG.")
        
        initial_results = self.vector_store.search(state["question"], k=1)
        
        if initial_results:
            doc, score = initial_results[0]
            steps.append(f"Contexto técnico encontrado. App: '{doc.metadata.get('gcp_service')}' com Score de similaridade: {score:.4f}")
            return {"retrieved_docs": [doc], "rag_score": float(score), "reasoning_steps": steps}
        
        steps.append("Nenhum contexto técnico relevante foi encontrado no RAG.")
        return {"retrieved_docs": [], "rag_score": 0.0, "reasoning_steps": steps}

    def _generate_filter(self, state: AgentState) -> dict:
        steps = state.get("reasoning_steps", [])
        steps.append("Invocando LLM para tradução da pergunta em filtro do GCP Cloud Logging.")
        
        if not state["retrieved_docs"]:
            return {"gcp_filter_query": "", "error_message": "Nenhum contexto técnico encontrado no RAG.", "reasoning_steps": steps}
            
        doc = state["retrieved_docs"][0]
        gcp_service = doc.metadata.get("gcp_service", "unknown")
        path = doc.metadata.get("path", "")
        
        error_context = ""
        if state.get("error_message"):
            error_context = f"\nATENÇÃO: Seu filtro anterior falhou com o erro: {state['error_message']}. Corrija a sintaxe imediatamente."
            steps.append(f"Reflexão ativada devido a falha anterior: {state['error_message']}")

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
            steps.append(f"Filtro gerado pela LLM: '{filter_string}'")
        except Exception as e:
            steps.append(f"Falha ao chamar a LLM: {str(e)}. Aplicando fallback interno.")
            filter_string = f'resource.labels.module_id="{gcp_service}" AND jsonPayload.message:"{path}"'
            
        return {"gcp_filter_query": filter_string, "reasoning_steps": steps}

    def _execute_gcp_query(self, state: AgentState) -> dict:
        steps = state.get("reasoning_steps", [])
        steps.append("Executando query de busca no ecossistema do GCP Cloud Logging.")
        
        logs, error_msg = execute_gcp_logging_query(state["gcp_filter_query"])
        
        if error_msg:
            steps.append(f"Erro de sintaxe retornado pela Tool: {error_msg}")
        else:
            steps.append(f"Sucesso na extração de logs. Quantidade de ocorrências recuperadas: {len(logs)}")
            
        return {
            "gcp_logs_result": logs, 
            "error_message": error_msg,
            "reasoning_steps": steps
        }

    def _synthesize_response(self, state: AgentState) -> dict:
        steps = state.get("reasoning_steps", [])
        steps.append("Enviando logs recuperados para a LLM sintetizar o resumo executivo de negócio.")
        
        user_message = f"User Question: {state['question']}\n\nGCP Logs Output:\n{str(state['gcp_logs_result'])}"
        
        messages = [
            SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
            HumanMessage(content=user_message)
        ]
        
        response = self.llm.invoke(messages)
        steps.append("Resposta final gerada com sucesso. Finalizando execução do grafo.")
        
        return {"final_response": response.content, "reasoning_steps": steps}

    def _route_after_query(self, state: AgentState) -> str:
        if state.get("error_message") and state.get("retry_count", 0) < 2:
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