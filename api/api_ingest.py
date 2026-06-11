# api/api_ingest.py
import os
import sys
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from dotenv import load_dotenv
import json
import asyncio
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector

from agent.graph import HermesGraphBuilder

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

load_dotenv()

app = FastAPI(
    title="Hermes NL2Query API",
    description="Engine unificada de ingestão RAG e execução de Agente para Observabilidade GCP",
    version="0.2.0"
)

PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_HOST = os.getenv("PG_HOST", "db") #
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB")

CONNECTION_STRING = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

embeddings_model = OllamaEmbeddings(
    model=os.getenv("EMBEDDING_MODEL", "mxbai-embed-large"),
    base_url=os.getenv("OLLAMA_HOST", "http://ollama:11434")
)

vector_store = PGVector(
    embeddings=embeddings_model,
    collection_name="hermes_openapi_spec",
    connection=CONNECTION_STRING,
    use_jsonb=True,
)

class VectorStoreManager:
    def __init__(self, db):
        self.db = db
    def search(self, query, k=2):
        return self.db.similarity_search_with_score(query, k=k)

vsm = VectorStoreManager(vector_store)
bot = HermesGraphBuilder(vector_store_manager=vsm)


# =====================================================================
# SCHEMAS PYDANTIC
# =====================================================================
class OpenAPISpecInput(BaseModel):
    openapi: str = Field(..., example="3.0.3")
    info: Dict[str, Any]
    paths: Dict[str, Dict[str, Any]]

class ChatInput(BaseModel):
    question: str = Field(..., example="Como está a taxa de erros na tela de impostos?")

class ChatResponse(BaseModel):
    reasoning_steps: List[str] = Field(..., description="Passo a passo da execução do grafo de agentes")
    response: str = Field(..., description="Resposta executiva sintetizada para o negócio")
    rag_score: float = Field(..., description="Score de similaridade da busca vetorial")


# =====================================================================
# AUXILIARES
# =====================================================================
def parse_spec_to_langchain_docs(paths: Dict[str, Any]) -> List[Document]:
    documents = []
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() not in ['get', 'post', 'put', 'delete', 'patch']:
                continue
                
            summary = details.get("summary", "Sem resumo disponível")
            description = details.get("description", "Sem descrição disponível")
            gcp_service = details.get("x-gcp-service", "unknown-service")
            
            natural_text = (
                f"O endpoint '{path}' responde ao método HTTP {method.upper()}. "
                f"Ele pertence e executa no microsserviço/app '{gcp_service}' dentro do Google Cloud Platform (GCP). "
                f"No Cloud Logging, este serviço é identificado por resource.labels.module_id='{gcp_service}' "
                f"ou resource.labels.configuration_name='{gcp_service}'. "
                f"Objetivo do endpoint: {summary}. "
                f"Funcionamento detalhado: {description}. "
                f"Termos de negócio relacionados e palavras-chave: {summary.lower()}, {gcp_service.replace('-', ' ')}."
            )
            
            metadata = {
                "path": path,
                "method": method.upper(),
                "gcp_service": gcp_service
            }
            documents.append(Document(page_content=natural_text, metadata=metadata))
    return documents


# =====================================================================
# ROTAS HTTP REST
# =====================================================================
@app.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_openapi_spec(spec: OpenAPISpecInput):
    try:
        lc_documents = parse_spec_to_langchain_docs(spec.paths)
        if not lc_documents:
            raise HTTPException(status_code=400, detail="No valid endpoint found on specification.")
            
        vector_store.add_documents(lc_documents)
        return {
            "status": "success",
            "message": f"Ingestion done. {len(lc_documents)} documents indexed."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@app.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_interaction_stream(payload: ChatInput):
    """
    Endpoint com streaming em tempo real (SSE) que expõe a execução 
    de cada nó do LangGraph conforme ele é processado.
    """
    initial_state = {
        "question": payload.question,
        "retrieved_docs": [],
        "rag_score": 0.0,
        "gcp_filter_query": "",
        "gcp_logs_result": [],
        "error_message": "",
        "retry_count": 0,
        "reasoning_steps": [],
        "final_response": ""
    }

    async def event_generator():
        try:
            loop = asyncio.get_event_loop()
            
            graph_stream = await loop.run_in_executor(
                None, 
                lambda: bot.graph.stream(initial_state, stream_mode="updates")
            )

            for update in graph_stream:
                node_name = list(update.keys())[0]
                node_data = update[node_name]
                
                latest_step = node_data.get("reasoning_steps", [])[-1] if node_data.get("reasoning_steps") else f"Nó {node_name} executado."
                
                chunk_data = {
                    "event": "node_update",
                    "node": node_name,
                    "reasoning_step": latest_step,
                    "rag_score": node_data.get("rag_score", None),
                    "response": node_data.get("final_response", None)
                }
                
                chunk_data = {k: v for k, v in chunk_data.items() if v is not None}
                
                yield {
                    "event": "message",
                    "data": json.dumps(chunk_data, ensure_ascii=False)
                }
                
                await asyncio.sleep(0.1)

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"detail": f"Erro no stream do grafo: {str(e)}"}, ensure_ascii=False)
            }

    return EventSourceResponse(event_generator())