# Fluxos da aplicação

Dois fluxos independentes, ligados apenas pela coleção no pgvector. A ingestão roda uma vez;
a busca roda a cada pergunta.

---

## 1. Ingestão do PDF

`python src/ingest.py`

```mermaid
flowchart LR
    PDF[("document.pdf<br/>34 páginas")]
    LOAD["PyPDFLoader<br/><i>load_pages</i>"]
    SPLIT["RecursiveCharacterTextSplitter<br/>1000 chars · overlap 150<br/><i>split_into_chunks</i>"]
    CLEAN["remove metadados vazios<br/><i>drop_empty_metadata</i>"]
    IDS["ids doc-0 … doc-66<br/><i>build_deterministic_ids</i>"]
    EMB["OpenAI<br/>text-embedding-3-small"]
    DB[("pgvector<br/>coleção desafio_rag<br/>67 chunks")]

    PDF --> LOAD --> SPLIT --> CLEAN --> IDS --> EMB --> DB

    classDef file fill:#e8eaf6,stroke:#5c6bc0,color:#1a237e
    classDef step fill:#e0f2f1,stroke:#26a69a,color:#004d40
    classDef ext fill:#fff3e0,stroke:#ffa726,color:#e65100
    class PDF,DB file
    class LOAD,SPLIT,CLEAN,IDS step
    class EMB ext
```

**Por que cada passo existe**

| Passo | Motivo |
|---|---|
| `overlap 150` | O PDF é uma tabela. O corte a cada 1000 caracteres parte linhas no meio; o overlap faz a linha partida reaparecer inteira no chunk seguinte |
| `drop_empty_metadata` | O `pypdf` devolve campos vazios (`creationdate: ''`) que sujariam o `jsonb` sem servir para nada |
| `build_deterministic_ids` | Ids posicionais tornam a reexecução um upsert — rodar duas vezes não duplica |

---

## 2. Pergunta e resposta

`python src/chat.py`

```mermaid
flowchart LR
    Q(["PERGUNTA<br/>do usuário"])
    EMBQ["OpenAI<br/>text-embedding-3-small"]
    SEARCH["similarity_search_with_score<br/>k = 10<br/><i>retrieve_context</i>"]
    DB[("pgvector<br/>coleção desafio_rag")]
    JOIN["junta os page_content<br/>dos 10 chunks"]
    PROMPT["PROMPT_TEMPLATE<br/>{contexto} + {pergunta}"]
    LLM["OpenAI<br/>gpt-5-nano · temp 0.3"]
    PARSE["StrOutputParser"]
    A(["RESPOSTA<br/>ou frase de recusa"])

    Q --> EMBQ --> SEARCH
    DB -.-> SEARCH
    SEARCH --> JOIN --> PROMPT --> LLM --> PARSE --> A
    Q -.->|passthrough| PROMPT

    classDef io fill:#f3e5f5,stroke:#ab47bc,color:#4a148c
    classDef step fill:#e0f2f1,stroke:#26a69a,color:#004d40
    classDef ext fill:#fff3e0,stroke:#ffa726,color:#e65100
    classDef file fill:#e8eaf6,stroke:#5c6bc0,color:#1a237e
    class Q,A io
    class SEARCH,JOIN,PROMPT,PARSE step
    class EMBQ,LLM ext
    class DB file
```

A pergunta segue por dois caminhos ao mesmo tempo: vira vetor para buscar os chunks que
preenchem o `{contexto}`, e chega intacta ao `{pergunta}` do template. É o que a chain LCEL
expressa:

```python
{
    "contexto": RunnableLambda(retrieve_context),
    "pergunta": RunnablePassthrough(),
}
| PromptTemplate.from_template(PROMPT_TEMPLATE)
| llm
| StrOutputParser()
```

**Onde a recusa acontece:** não há filtro por score. Os 10 chunks vêm sempre, relevantes ou
não. Quem decide recusar é o `PROMPT_TEMPLATE`, ao constatar que a resposta não está no
`{contexto}`.

---

## Os dois fluxos lado a lado

```mermaid
flowchart LR
    subgraph ING["Ingestão · uma vez"]
        direction LR
        P[("PDF")] --> C["chunks<br/>1000/150"] --> E1["embeddings"]
    end

    DB[("pgvector<br/>desafio_rag")]

    subgraph BUSCA["Busca · a cada pergunta"]
        direction LR
        Q(["pergunta"]) --> E2["embedding"] --> K["top 10"] --> L["LLM"] --> R(["resposta"])
    end

    E1 --> DB
    DB -.-> K

    classDef file fill:#e8eaf6,stroke:#5c6bc0,color:#1a237e
    classDef step fill:#e0f2f1,stroke:#26a69a,color:#004d40
    classDef io fill:#f3e5f5,stroke:#ab47bc,color:#4a148c
    class P,DB file
    class C,E1,E2,K,L step
    class Q,R io
```

O acoplamento entre os dois é uma variável só: `PG_VECTOR_COLLECTION_NAME`. E uma regra —
**os dois lados precisam usar o mesmo modelo de embeddings**. Vetores de modelos diferentes não
são comparáveis, e a busca degradaria em silêncio. É por isso que `ingest.py` e `search.py`
pedem o modelo ao `providers.py` em vez de instanciarem o seu próprio.
