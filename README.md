# NL2Query: RAG + GCP Observability POC 🚀

## 🎯 Goal
Proof of Concept (POC) to validate building a natural language interface (Text-to-Query) capable of querying logs and metrics in GCP Cloud Logging. The solution uses RAG (Retrieval-Augmented Generation) to correlate the user's business intent with the technical infrastructure (routes, microservices, and labels) without requiring static dictionaries.

## 🏗️ System Architecture

The system is divided into two independent major flows: the **Data Ingestion Pipeline (Data Prep)** and the **Execution Engine (Runtime/LangGraph)**.

### 1. Architecture Overview

```mermaid
graph TD
    %% Cores e Estilos
    classDef user fill:#2d3436,stroke:#74b9ff,stroke-width:2px,color:#fff
    classDef pipeline fill:#0984e3,stroke:#74b9ff,stroke-width:2px,color:#fff
    classDef database fill:#00b894,stroke:#55efc4,stroke-width:2px,color:#fff
    classDef runtime fill:#6c5ce7,stroke:#a29bfe,stroke-width:2px,color:#fff
    classDef external fill:#d63031,stroke:#ff7675,stroke-width:2px,color:#fff

    User((User / Product)):::user
    
    subgraph Flow 1: Data Ingestion
        Swagger[Swagger/OpenAPI JSON]:::external
        Parser[Python NLP Parser]:::pipeline
        Embedder[Embedding Model]:::pipeline
        PGVector[(PostgreSQL + pgvector)]:::database
        
        Swagger -->|Reads API definitions| Parser
        Parser -->|Converts to Natural Language| Embedder
        Embedder -->|Generates Vectors| PGVector
    end

    subgraph Flow 2: Runtime
        API[FastAPI / Webhook]:::runtime
        Harness[LangGraph Agent]:::runtime
        LLM[LLM Engine]:::external
        GCP[GCP Cloud Logging]:::external
        
        User -->|Question in PT-BR| API
        API --> Harness
        Harness <-->|Semantic Search| PGVector
        Harness <-->|Generates Filter String| LLM
        Harness <-->|Executes Safe Query| GCP
        Harness <-->|Synthesizes Answer| LLM
    end
    
    %% Final Connection
    Harness -->|Formatted Response| API
    API --> User
```

### 2. LangGraph Execution Flow (Harness)
Below is the decision graph detail that the agent executes for each new request.

```mermaid
flowchart TD
    Start((Start)) --> Receives_Query[Receives Query]
    
    Receives_Query -- How many errors in the tax API? --> Semantic_Search_In

    subgraph Semantic_Search [Node: Semantic Search]
        Semantic_Search_In[RAG Query] -->|Cosine Similarity| PGVector[(PGVector)]
        PGVector -->|Returns app and routes| Retrieved_Context[Retrieved Context]
    end

    Retrieved_Context --> Generates_GCP_Filter_In

    subgraph Generates_GCP_Filter [Node: GCP Filter Generation]
        Generates_GCP_Filter_In[Builds Prompt] -->|Question + Context| Calls_LLM{LLM Engine}
        Calls_LLM -->|Returns e.g. resource.labels...| Validate_Syntax[Validate Syntax]
    end

    Validate_Syntax --> Executes_GCP_SDK[Node: Execute GCP SDK]

    Executes_GCP_SDK -- SDK Error --> Reflection[Autocorrection / Reflection]
    Reflection -->|Adjusts prompt with error| Generates_GCP_Filter_In

    Executes_GCP_SDK -- Returns Log JSON --> Synthesizes_Response[Node: Synthesizes Response]

    Synthesizes_Response --> Responds_User[Responds to User]
    Responds_User --> End((End))
    
    %% Error flow styling to draw attention
    style Reflection fill:#ff7675,stroke:#d63031,stroke-width:2px,color:#fff
```
## 🛠️ Technology Stack (POC)

### Ingestion Flow (Data Pipeline)
* **Language**: Python 3.11+
* **Processing**: LangChain / LlamaIndex (for chunking and NLP parsing)
* **Database**: PostgreSQL (via Docker) with the pgvector extension
* **Embeddings**: Google Gemini embedding models (or OpenAI/Local text-embedding-3)

### Runtime Flow (Agent)
* **Web Framework**: FastAPI
* **AI Orchestration**: LangGraph (state, node, and routing cycle management)
* **LLM Core**: Gemini 1.5 Pro / GPT-4o (filter code generation and synthesis)
* **Cloud Integration**: google-cloud-logging SDK