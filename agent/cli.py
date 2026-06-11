import os
import sys
from dotenv import load_dotenv

# Importa o builder do grafo que acabamos de estruturar
from graph import HermesGraphBuilder

# Importa os wrappers oficiais do seu ecossistema de sucesso
from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector

from graph import HermesGraphBuilder
import graph as graph_module
print(f"📍 ORIGEM DO GRAFO: {graph_module.__file__}")

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

load_dotenv()

# =====================================================================
# 1. ENCAPSULAMENTO DO VECTOR STORE (IDÊNTICO AO SEU PADRÃO)
# =====================================================================
class VectorStoreManager:
    def __init__(self):
        self.embeddings = OllamaEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "mxbai-embed-large"),
            base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434")
        )
        
        pg_user = os.getenv("PG_USER", "hermes")
        pg_password = os.getenv("PG_PASSWORD", "hermes_password")
        pg_host = os.getenv("PG_HOST", "localhost") # localhost para rodar direto da máquina apontando pro container
        pg_port = os.getenv("PG_PORT", "5432")
        pg_db = os.getenv("PG_DB", "hermes_rag")
        
        connection_string = f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        
        self.db = PGVector(
            embeddings=self.embeddings,
            collection_name="hermes_openapi_spec",
            connection=connection_string,
            use_jsonb=True,
        )

    def search(self, query, k=2):
        # Retorna o resultado estruturado que o grafo espera
        return self.db.similarity_search_with_score(query, k=k)


# =====================================================================
# 2. LOOP DE EXECUÇÃO DA CLI
# =====================================================================
def start_cli():
    print("\n" + "="*60)
    print("🤖 HERMES NL2QUERY AGENT - INTERACTIVE CLI (POC)")
    print("="*60)
    print("Inicializando componentes e malha do LangGraph...")
    
    try:
        # Inicializa o gerenciador de vetores e injeta no grafo
        vsm = VectorStoreManager()
        bot = HermesGraphBuilder(vector_store_manager=vsm)
        print("✅ Sistema pronto! Digite sua pergunta de negócio abaixo.")
        print("(Digite 'sair' ou 'exit' para encerrar o terminal)\n")
    except Exception as e:
        print(f"❌ Erro crítico na inicialização do ecossistema: {e}")
        return

    while True:
        try:
            user_input = input("👤 Você: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["sair", "exit"]:
                print("\nEncerrando sessão do Hermes. Até a próxima, comandante! 🚀")
                break
            
            # Inicializa o estado para rodar a malha do LangGraph
            initial_state = {
                "question": user_input,
                "retrieved_docs": [],
                "gcp_filter_query": "",
                "gcp_logs_result": [],
                "error_message": "",
                "retry_count": 0,
                "final_response": ""
            }
            
            # Executa o grafo compilado invocando todos os nós em sequência
            final_state = bot.graph.invoke(initial_state)
            
            print("\n🤖 Hermes:")
            print(final_state.get("final_response", "❌ Falha ao sintetizar resposta."))
            print("-" * 60 + "\n")
            
        except KeyboardInterrupt:
            print("\n\nSessão encerrada via atalho de terminal.")
            break
        except Exception as e:
            print(f"\n❌ Ocorreu um erro durante a execução do grafo: {e}\n")

if __name__ == "__main__":
    start_cli()