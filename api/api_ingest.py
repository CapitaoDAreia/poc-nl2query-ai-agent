import os
import sys
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

load_dotenv()

app = FastAPI(
    title="Hermes Ingestion API",
    description="Process API specification into langchain documents",
    version="0.1.0"
)

PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")
PG_DB = os.getenv("PG_DB")

CONNECTION_STRING = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

embeddings_model = OllamaEmbeddings(
    model=os.getenv("EMBEDDING_MODEL", "mxbai-embed-large"),
    base_url=os.getenv("OLLAMA_HOST", "http://ollama:11434") #Ollama Inference Server
)

vector_store = PGVector(
    embeddings=embeddings_model,
    collection_name="hermes_openapi_spec",
    connection=CONNECTION_STRING,
    use_jsonb=True,
)

class OpenAPISpecInput(BaseModel):
    openapi: str = Field(..., example="3.0.3")
    info: Dict[str, Any]
    paths: Dict[str, Dict[str, Any]]

def parse_spec_to_langchain_docs(paths: Dict[str, Any]) -> List[Document]:
    """Parse API specification to documents to be stored."""
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
        raise HTTPException(status_code=500, detail=f"Failed on processo document: {str(e)}")