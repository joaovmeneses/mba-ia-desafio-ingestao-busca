# Fluxos da aplicação

Dois fluxos independentes, ligados apenas pela coleção no pgvector. A ingestão roda uma vez;
a busca roda a cada pergunta.

---

## 1. Ingestão do PDF

`python src/ingest.py`

```mermaid
flowchart LR
    A[document.pdf]
    B[PyPDFLoader]
    C[Split 1000/150]
    D[Limpa metadados]
    E[Gera ids]
    F[Embeddings]
    G[(pgvector)]

    A --> B --> C --> D --> E --> F --> G

    classDef dado fill:#e8eaf6,stroke:#5c6bc0
    classDef passo fill:#e0f2f1,stroke:#26a69a
    classDef api fill:#fff3e0,stroke:#ffa726
    class A,G dado
    class B,C,D,E passo
    class F api
```

| Etapa | O que acontece | Por que existe |
|---|---|---|
| `PyPDFLoader` | 34 páginas viram Documents | — |
| Split | 1000 caracteres, overlap 150 → 67 chunks | O PDF é uma tabela: o corte parte linhas no meio, e o overlap faz a linha partida reaparecer inteira no chunk seguinte |
| Limpa metadados | Remove campos vazios | O `pypdf` devolve `creationdate: ''`, que sujaria o `jsonb` sem servir para nada |
| Gera ids | `doc-0` … `doc-66` | Ids posicionais tornam a reexecução um upsert — rodar duas vezes não duplica |
| Embeddings | `text-embedding-3-small`, 1536 dimensões | — |

---

## 2. Pergunta e resposta

`python src/chat.py`

```mermaid
flowchart LR
    Q[Pergunta]
    E[Embedding]
    S[Busca k=10]
    DB[(pgvector)]
    C[Monta contexto]
    P[Prompt]
    L[gpt-5-nano]
    R[Resposta]

    Q --> E --> S --> C --> P --> L --> R
    DB -.-> S
    Q -.-> P

    classDef dado fill:#e8eaf6,stroke:#5c6bc0
    classDef passo fill:#e0f2f1,stroke:#26a69a
    classDef api fill:#fff3e0,stroke:#ffa726
    classDef io fill:#f3e5f5,stroke:#ab47bc
    class Q,R io
    class S,C,P passo
    class E,L api
    class DB dado
```

A linha pontilhada de `Pergunta` para `Prompt` é o segundo caminho: a pergunta vira vetor para
buscar os chunks que preenchem o `contexto`, e ao mesmo tempo chega intacta ao template. É o que
a chain expressa:

```python
{
    "contexto": RunnableLambda(retrieve_context),
    "pergunta": RunnablePassthrough(),
}
| PromptTemplate.from_template(PROMPT_TEMPLATE)
| llm
| StrOutputParser()
```

**Onde a recusa acontece:** não há filtro por score. Os 10 chunks vêm sempre, relevantes ou não.
Quem decide recusar é o `PROMPT_TEMPLATE`, ao constatar que a resposta não está no contexto.

---

## Os dois fluxos lado a lado

```mermaid
flowchart LR
    subgraph ING[Ingestao - uma vez]
        P[PDF] --> C[Chunks] --> E1[Embeddings]
    end

    DB[(pgvector)]

    subgraph BUSCA[Busca - a cada pergunta]
        Q[Pergunta] --> E2[Embedding] --> K[Top 10] --> L[LLM] --> R[Resposta]
    end

    E1 --> DB
    DB -.-> K

    classDef dado fill:#e8eaf6,stroke:#5c6bc0
    classDef passo fill:#e0f2f1,stroke:#26a69a
    class P,DB dado
    class C,E1,Q,E2,K,L,R passo
```

O acoplamento entre os dois é uma variável só: `PG_VECTOR_COLLECTION_NAME`. E uma regra — **os
dois lados precisam usar o mesmo modelo de embeddings**. Vetores de modelos diferentes não são
comparáveis, e a busca degradaria em silêncio. É por isso que `ingest.py` e `search.py` pedem o
modelo ao `providers.py` em vez de instanciarem o seu próprio.
