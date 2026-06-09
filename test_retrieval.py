import os
import sys
from dotenv import load_dotenv

# Componentes do LangChain para recuperar os dados
from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

load_dotenv()

# Mesma configuração de conexão utilizada na Ingestão
PG_USER = os.getenv("PG_USER", "hermes")
PG_PASSWORD = os.getenv("PG_PASSWORD", "hermes_password")
PG_HOST = os.getenv("PG_HOST", "localhost") # "localhost" pois vamos rodar o script direto da máquina apontando pro container
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "hermes_rag")

CONNECTION_STRING = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

def run_test_search(query: str, k: int = 2):
    print(f"\n🔍 Realizando busca semântica para: '{query}'")
    print("-" * 60)
    
    # Inicializa o modelo de embeddings (Ollama deve estar rodando)
    embeddings_model = OllamaEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "mxbai-embed-large"),
        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    
    # Conecta no Vector Store existente
    vector_store = PGVector(
        embeddings=embeddings_model,
        collection_name="hermes_openapi_spec",
        connection=CONNECTION_STRING,
    )
    
    # Executa a busca trazendo o score de distância (quanto menor, mais próximo)
    results = vector_store.similarity_search_with_score(query, k=k)
    
    if not results:
        print("❌ Nenhum documento correspondente encontrado no banco vetorial.")
        return

    for idx, (doc, score) in enumerate(results, 1):
        print(f"\n[Resultado #{idx}] - Score de Distância: {score:.4f}")
        print(f"📌 Caminho (Path): {doc.metadata.get('path')}")
        print(f"🚀 Método: {doc.metadata.get('method')}")
        print(f"📦 Serviço GCP: {doc.metadata.get('gcp_service')}")
        print(f"📖 Texto Recuperado:\n   {doc.page_content}")
        print("=" * 60)

if __name__ == "__main__":
    # Teste 1: Focado no microsserviço de impostos que quebrou em produção
    pergunta_teste = "Quantos erros aconteceram na API de impostos?"
    run_test_search(pergunta_teste, k=1)
    
    # Teste 2: Focado em outro contexto para validar se ele diferencia bem os microsserviços
    # pergunta_teste_2 = "Tivemos alguma falha ao emitir nota fiscal na prefeitura?"
    # run_test_search(pergunta_teste_2, k=1)