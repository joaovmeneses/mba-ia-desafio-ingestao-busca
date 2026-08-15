# Plano de Implementação — Desafio RAG (Ingestão + Busca)

> Documento vivo. Serve para revisão antes da execução e para registrar decisões conforme forem sendo tomadas.
> **Status geral:** **M0, M1, M2.0 e M2 concluídas.** 67 chunks ingeridos e retrieval validado. Próxima: **M3 — busca e chain**.
> Última atualização: 2026-08-15.

---

## 1. Avaliação do que temos hoje

### 1.1 Estado do repositório

Fork do skeleton oficial, em paridade **byte-a-byte** com `upstream/main` (`82d86ce`). A única diferença local é o `CLAUDE.md` que adicionamos. Não há `git pull` pendente; o upstream não recebe commit desde 2025-08-29 e não tem branch de solução, tag ou release.

| Arquivo | Estado |
|---|---|
| `docker-compose.yml` | ✅ Pronto. `pgvector/pgvector:pg17` + serviço one-shot `bootstrap_vector_ext` que roda `CREATE EXTENSION vector` |
| `requirements.txt` | ✅ Pronto. Já traz OpenAI **e** Google, `langchain-postgres==0.0.15`, `pypdf`, `psycopg` |
| `.env.example` | ⚠️ Incompleto — só tem `*_EMBEDDING_MODEL`, **falta variável do modelo de chat** |
| `document.pdf` | ✅ Presente (175 KB) |
| `src/ingest.py` | ⛔ Stub — `def ingest_pdf(): pass` |
| `src/search.py` | ⛔ Stub — `PROMPT_TEMPLATE` pronto, `def search_prompt(question=None): pass` |
| `src/chat.py` | ⛔ Stub — `main()` com early-return, corpo `pass` |
| `README.md` | ⛔ Stub — "Descreva abaixo como executar a sua solução." (é item de entrega) |

### 1.2 O `document.pdf` é uma **tabela**, não prosa

Este é o achado que mais influencia o plano. Decodificando os streams do PDF:

- **~34–36 páginas**, título de metadata `"Planilha sem título"`.
- 3 colunas: `Nome da empresa | Faturamento | Ano de fundação`.
- **~1.084–1.103 linhas** de empresas sintéticas (`Alfa Agronegócio Indústria`, `Alfa Energia Holding`, `Aurora Educação EPP`, `SuperTechIABrazil`, …).
- ~1.400 caracteres de texto por página → **~50 KB de texto total → ~55–65 chunks** com `chunk_size=1000`.

Consequências diretas:

1. Chunking de 1000 chars **corta linhas da tabela no meio**. O `overlap=150` é justamente o que garante que a linha partida reapareça inteira no chunk seguinte. **Não reduzir o overlap** para "otimizar".
2. `k=10` sobre ~60 chunks significa recuperar **~1/6 do documento inteiro** a cada pergunta. É generoso de propósito — compensa a fragmentação da tabela. Contexto resultante: ~10 KB ≈ 2,5k tokens por chamada. Custo e latência são irrelevantes nessa escala.
3. Busca semântica sobre tabela é fraca por natureza — o que salva é o **nome da empresa aparecer literalmente** no chunk. Perguntas por nome exato funcionam; perguntas agregadas ("quantas empresas...", "qual a maior...") **não vão funcionar** e devem cair na recusa. Isso é comportamento correto, não bug.

### 1.3 Ambiente local

| Item | Estado |
|---|---|
| Docker / Compose | ✅ 28.5.1 / v2.40.3 — nenhum container de pé |
| Python do sistema | ⛔ 3.9.6 — **não serve** (`numpy==2.3.2` exige ≥3.11) |
| Python utilizável | ✅ `python3.12` e `python3.13` via homebrew |
| venv | ⛔ Não criado |
| `.env` | ⚠️ Criado, com 3 correções pendentes (B1–B4 abaixo) |
| `OPENAI_API_KEY` | ✅ Preenchida |
| Porta 5432 do host | ⛔ Ocupada pelo backend do Docker → daí a mudança de porta |

### 1.4 Bloqueadores no estado atual (⚠️ resolver na M0)

Encontrados na revalidação de 2026-08-15. Não são edge cases — impedem a M0 de rodar.

| # | Problema | Evidência / correção |
|---|---|---|
| **B1** | `docker-compose.yml` mapeia a porta **75432**, que é inválida (TCP vai até 65535) | `docker compose config` → `invalid hostPort: 75432`. Corrigir para `"55432:5432"` (55432 verificada como livre) |
| **B2** | O `bootstrap_vector_ext` aponta para `postgres:75432` na **rede interna** | Container↔container usa sempre a porta **interna** (5432); o host port é irrelevante ali. Voltar para `postgresql://postgres:postgres@postgres:5432/rag`. **Independente da B1** — continua quebrado mesmo com host port válido |
| **B3** | `DATABASE_URL` sem sufixo de driver (viola D8) | `postgresql://` faz o SQLAlchemy escolher psycopg2. Corrigir para `postgresql+psycopg://postgres:postgres@localhost:55432/rag` |
| **B4** | `PDF_PATH=./document.pdf` é relativo ao cwd | Funciona da raiz, quebra de dentro de `src/`. Resolver no código na M2 (§M2) |

> Consequência de B2 se passar batido: o bootstrap tem `restart: "no"` e falha em silêncio; a ingestão só quebra depois, com `type "vector" does not exist` — que é o R2 chegando por outra porta. Por isso o check `\dx` da M0 não é opcional.

---

## 2. Avaliação do enunciado

### 2.1 O que o enunciado exige (transcrito do briefing)

| Requisito | Valor |
|---|---|
| Linguagem / framework | Python + LangChain |
| Banco | PostgreSQL + pgVector via Docker Compose |
| Chunk size / overlap | 1000 / 150 |
| Busca | `similarity_search_with_score(query, k=10)` |
| Loader | `PyPDFLoader` |
| Splitter | `RecursiveCharacterTextSplitter` |
| Vector store | `PGVector` (`langchain_postgres`) |
| Embeddings | `text-embedding-3-small` (OpenAI) ou `models/embedding-001` (Gemini) |
| LLM | `gpt-5-nano` |
| Interface | CLI simulando chat |
| Fluxo da busca | vetorizar pergunta → buscar k=10 → montar prompt → chamar LLM → responder |

### 2.2 O enunciado **não está no repositório**

Verificado: o README do upstream tem 2 linhas. Requisitos, critérios de avaliação e instruções de entrega vivem na plataforma da Full Cycle. Busca por código no GitHub em repos de alunos não encontrou transcrição literal.

**Implicação:** o briefing que você colou é a fonte da verdade — **confirmado em 2026-08-15**: a plataforma não traz critérios de avaliação além do que já está no briefing. Os parâmetros acima foram ainda **corroborados de forma independente** por múltiplas entregas de alunos (PRs #21, #36, #39 do upstream).

Um sinal de confirmação útil: o **PR #19** do upstream é exatamente alguém corrigindo `overlap` de 200 → 150. Ou seja, 150 é o valor esperado e 200 é um erro comum de quem seguiu exemplo de aula.

### 2.3 Contratos implícitos nos stubs (não quebrar)

Os stubs codificam decisões que a avaliação provavelmente espera:

1. **`search_prompt()` é chamado sem argumentos e deve devolver uma _chain_**, não uma resposta. O `chat.py` faz `chain = search_prompt()` e testa `if not chain:`. Retornar `None` ou string quebra o fluxo.
2. **A assinatura é `search_prompt(question=None)`** — o parâmetro existe mas o `chat.py` não usa. Manter a assinatura por compatibilidade.
3. **Os placeholders do `PROMPT_TEMPLATE` são `{contexto}` e `{pergunta}`** — em português. As chaves do `invoke()` têm que bater exatamente.
4. **`PROMPT_TEMPLATE` é artefato avaliado.** A frase de recusa `"Não tenho informações necessárias para responder sua pergunta."` precisa sair literal. Não reescrever nem suavizar o template.
5. **Imports flat**: `chat.py` faz `from search import search_prompt`. Roda como `python src/chat.py` a partir da raiz (o diretório do script entra no `sys.path`). `python -m src.chat` quebra sem `__init__.py`.

### 2.4 Perguntas-canário (teste de aceite)

Recorrentes em todas as entregas analisadas:

| Pergunta | Resposta esperada |
|---|---|
| Qual o faturamento da Empresa SuperTechIABrazil? | R$ 10.000.000,00 (ano 2025) ✅ **conferido no PDF** |
| Qual foi o ano de fundação e faturamento da empresa Aurora Educação EPP? | 1958 / R$ 4.321.211.894,95 ✅ **conferido no PDF** |
| Quantos clientes temos em 2024? | Não tenho informações necessárias para responder sua pergunta. |
| Qual é o tamanho da base de dados? | Não tenho informações necessárias para responder sua pergunta. |
| Qual é a capital da França? | Não tenho informações necessárias para responder sua pergunta. |

> ✅ **Conferido na M2.0 (2026-08-15):** os dois valores, que vinham de READMEs de alunos, batem exatamente com o PDF real. O gabarito está validado.
>
> Par adicional para o teste de nomes colidentes (E7), extraído do PDF:
> `Alfa Energia Holding` = R$ 858.537,02 (1971) · `Alfa Energia S.A.` = R$ 722.875.391,46 (1972).

---

## 3. Avaliação dos repositórios de referência

### 3.1 `devfullcycle/mba-ia-niv-introducao-langchain` (repo de aula)

Padrões do professor, extraídos dos 19 arquivos do repo:

- **Scripts procedurais.** Zero classes no repo inteiro. Sem `main()`, sem `if __name__ == "__main__"`, sem `argparse`.
- **`PGVector` sempre com 4 kwargs**, nesta ordem: `embeddings`, `collection_name`, `connection`, `use_jsonb=True`. Nunca `from_documents`, nunca `pre_delete_collection`, nunca `distance_strategy`. Variável sempre chamada `store`.
- **Split idêntico ao do desafio**: `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150, add_start_index=False)`.
- **Higiene de metadata antes de indexar** — reconstrói os `Document` filtrando chaves vazias, o que evita sujeira no `jsonb`:
  ```python
  enriched = [Document(page_content=d.page_content,
                       metadata={k: v for k, v in d.metadata.items() if v not in ("", None)})
              for d in splits]
  ids = [f"doc-{i}" for i in range(len(enriched))]
  store.add_documents(documents=enriched, ids=ids)
  ```
- **Validação de config é um loop literal:**
  ```python
  for k in ("OPENAI_API_KEY", "PGVECTOR_URL", "PGVECTOR_COLLECTION"):
      if not os.getenv(k):
          raise RuntimeError(f"Environment variable {k} is not set")
  ```
- **`python-dotenv` + `os.getenv` direto.** `pydantic-settings` está no requirements mas **nunca é importado** — não usar.
- **LCEL com pipe `|` é o padrão dominante**, com `StrOutputParser()` e `RunnableLambda` para adaptar shapes entre estágios.
- **`similarity_search_with_score` é a única API de busca do repo.** `as_retriever` e `similarity_search` não aparecem.
- Idioma: código e nomes em inglês, saídas para o usuário em português.

**O gap crítico:** o repo de aula **não tem nenhuma chain de RAG**. O módulo 5 para na busca vetorial e imprime resultados — não existe a ponte "documentos recuperados → prompt → LLM". `create_retrieval_chain`, `RetrievalQA` e `as_retriever` não existem no repo. Também não existe CLI interativo (a query é constante hardcoded). **Essas duas peças são invenção nossa** — é exatamente o que o desafio pede.

### 3.2 `devfullcycle/mba-ia-desafio-ingestao-busca` (skeleton)

Além da paridade já descrita em §1.1, dois achados dos PRs abertos:

- **PR #6 — race condition no `bootstrap_vector_ext`.** O healthcheck passa antes do Postgres aceitar conexão de forma confiável. Se a ingestão falhar com `type "vector" does not exist`, é isso. Contorno **sem tocar no compose**: `docker compose restart bootstrap_vector_ext`. Na prática costuma passar batido porque `langchain-postgres` 0.0.15 também tenta criar a extensão sozinho.
- **PR #19** — confirma overlap 150 (ver §2.2).

---

## 4. Arquitetura proposta

### 4.1 SOLID aplicado de forma proporcional

O projeto tem ~200 linhas de código útil. SOLID aqui significa **separar responsabilidades e inverter a dependência de provider** — nada além disso.

| Princípio | Como aplicamos | Custo |
|---|---|---|
| **SRP** | Um módulo por responsabilidade: config, providers, store, ingestão, busca, CLI | 3 arquivos novos, todos curtos |
| **DIP** | `ingest.py` e `search.py` **nunca** instanciam `OpenAIEmbeddings`/`ChatOpenAI` direto — pedem a `providers.get_embeddings()` / `get_llm()` | 1 função-fábrica cada |
| **OCP** | Trocar OpenAI ↔ Gemini = mexer só em `providers.py`. Nenhum outro arquivo muda | grátis, consequência do DIP |
| **LSP / ISP** | Já resolvidos pelo LangChain — `Embeddings`, `BaseChatModel` e `Runnable` são as interfaces. **Não criar ABCs próprias em cima delas** | zero |

**Anti-overengineering — o que NÃO vamos fazer** (registro explícito para não escorregar durante a execução):

- ❌ Classes de repositório / `VectorStoreRepository` envolvendo `PGVector`
- ❌ Arquitetura hexagonal, camadas `domain/application/infra`
- ❌ Container de injeção de dependência
- ❌ `pydantic-settings` / classe `Settings` (o professor não usa; `os.getenv` basta)
- ❌ ABCs ou `Protocol` próprios para embeddings/LLM
- ❌ Logging estruturado, retry, cache, métricas
- ❌ Async

### 4.2 Estrutura de arquivos

```
src/
  config.py      # NOVO  — load_dotenv + leitura e validação das env vars
  providers.py   # NOVO  — get_embeddings() / get_llm(): resolve provider por env  [DIP]
  store.py       # NOVO  — get_vector_store(): monta o PGVector
  ingest.py      # EXISTE — entrypoint de ingestão, mantém ingest_pdf()
  search.py      # EXISTE — PROMPT_TEMPLATE (intocado) + search_prompt() devolve a chain
  chat.py        # EXISTE — entrypoint CLI, mantém main()
docs/
  plan.md        # este documento
```

Todos com **import flat** (`from config import ...`), preservando o contrato do skeleton. Execução a partir da raiz: `python src/ingest.py`, `python src/chat.py`.

### 4.3 Fluxo

**Ingestão** (`python src/ingest.py`, roda uma vez):
```
PDF_PATH → PyPDFLoader.load()
         → RecursiveCharacterTextSplitter(1000, 150).split_documents()
         → higiene de metadata + ids determinísticos
         → store.add_documents()
```

**Busca** (`search_prompt()` devolve a chain; `chat.py` invoca por pergunta):
```
pergunta (str)
  ├─ RunnableLambda: store.similarity_search_with_score(q, k=10) → join dos page_content → {contexto}
  └─ RunnablePassthrough → {pergunta}
        → PromptTemplate.from_template(PROMPT_TEMPLATE)
        → llm
        → StrOutputParser()
        → resposta (str)
```

A chain aceita a pergunta como **string** e devolve string. Toda a construção (embeddings, store, llm) acontece **uma vez**, na chamada de `search_prompt()` — o loop do CLI só faz `chain.invoke(pergunta)`.

---

## 5. Registro de decisões

Formato: `Aberta` = precisa de definição antes/durante a execução · `Decidida` = fechada, com racional.

| ID | Decisão | Status | Racional |
|---|---|---|---|
| **D1** | **Provider: OpenAI, Gemini ou ambos?** | 🟢 Decidida (2026-08-15) | **OpenAI**: `gpt-5-nano` + `text-embedding-3-small` — é o que o enunciado nomeia. `providers.py` fica estruturado para aceitar Gemini sem refactor, mas **só OpenAI é implementado**. |
| **D2** | Estrutura: 3 arquivos flat vs. pacote `src/rag/` | 🟢 Decidida | 6 arquivos flat em `src/`. Pacote quebraria `from search import search_prompt` do stub, que é contrato de avaliação. |
| **D3** | `similarity_search_with_score(k=10)` vs `as_retriever()` | 🟢 Decidida | `similarity_search_with_score` — está no enunciado *e* é a única API de busca do repo de aula. `as_retriever` seria mais idiomático em RAG genérico, mas foge do especificado. |
| **D4** | Forma da chain | 🟢 Decidida | LCEL manual (§4.3). `create_retrieval_chain`/`RetrievalQA` não aparecem em nenhum dos repos de referência. |
| **D5** | Chunk 1000 / overlap 150 / `add_start_index=False` | 🟢 Decidida | Enunciado + repo de aula + PR #19 convergem. Não ajustar mesmo que a retrieval pareça ruim. |
| **D6** | Idempotência da ingestão | 🟢 Decidida (revisada) | IDs determinísticos `doc-{i}` → re-executar `ingest.py` faz **upsert**, não duplica. **Ressalva (E2):** só vale se a contagem de chunks não diminuir. Ver D16. |
| **D7** | Variável do modelo de chat | 🟢 Decidida | `.env.example` não tem. Adicionar `OPENAI_CHAT_MODEL=gpt-5-nano` (e `GOOGLE_CHAT_MODEL` se D1 incluir Gemini). Como `.env.example` é item de entrega, atualizar lá também. |
| **D8** | Formato do `DATABASE_URL` | 🟢 Decidida | `postgresql+psycopg://postgres:postgres@localhost:5432/rag`. `langchain-postgres` 0.0.15 exige o sufixo de driver SQLAlchemy; `postgresql://` puro falha. |
| **D9** | Coleção por provider | ⚪ Não se aplica | Resolvida por D1 (só OpenAI) — uma coleção só. Se um dia entrar Gemini, aí sim precisa de coleção separada: dimensões e espaços semânticos diferentes não são comparáveis. |
| **D10** | Testes automatizados | 🟢 Decidida | **Sem pytest.** Não está no `requirements.txt`, não existe em nenhum repo de referência e o desafio não pede. Validação = checklist de perguntas-canário na M5. Adicionar pytest seria overengineering para 200 linhas. |
| **D11** | Python 3.12 no venv | 🟢 Decidida | Sistema tem 3.9.6, insuficiente para `numpy==2.3.2` (≥3.11). Homebrew tem 3.12 e 3.13; fixar 3.12 por ser a mais rodada com esse stack. |
| **D12** | Parâmetros do LLM (família gpt-5) | 🟢 **Fechada na M1** — `temperature=0.3` aceito por `gpt-5-nano`; sem resposta vazia | Ampliada por E5. Três frentes: (a) **`temperature` = `0.3`** (decidido 2026-08-15); a família gpt-5 costuma exigir `1`, então se a API recusar, **omitir o parâmetro**; (b) **resposta vazia** — modelo de reasoning pode gastar o budget no raciocínio e devolver `content` vazio; não limitar `max_tokens` sem necessidade; (c) **modelo indisponível** no tier da chave → ver D17. Decidir com o erro real na mão. |
| **D13** | Porta do Postgres | 🟢 Decidida (2026-08-15) | **`"55432:5432"`** — 55432 no host (verificada livre), 5432 interno. A 5432 do host está ocupada pelo backend do Docker. Corrige B1+B2+B3 juntos. Aceita-se o diff no `docker-compose.yml` em relação ao upstream; documentar o motivo no README. |
| **D14** | `search_prompt(question=None)` com argumento | 🟢 Decidida (2026-08-15) | **Suportar os dois modos.** Sem argumento → devolve a chain (o que `chat.py` usa). Com pergunta → invoca e devolve a resposta em `str`. ~3 linhas, defende contra avaliação automática que chame de outra forma. |
| **D15** | Threshold de score na busca | 🟢 Decidida | **Não aplicar.** O enunciado fixa `k=10`; toda pergunta fora de contexto vai receber 10 chunks irrelevantes e a recusa depende **inteiramente** do `PROMPT_TEMPLATE`. É by design — registrado para não sermos tentados a "consertar" depois. Os scores são descartados (mas ver E3: a API devolve tuplas). |
| **D16** | Limpeza ao mudar parâmetros de chunking | 🟢 Decidida (2026-08-15) | Mudança em `chunk_size`/`overlap`/provider exige **dropar a coleção antes de re-ingerir** — senão sobram vetores órfãos de índice alto (E2). Documentar no README + comando pronto na M2. |
| **D17** | Plano B de modelo | ⚪ **Não necessário** — `gpt-5-nano` disponível (verificado na M1); mantido só como contingência | Se `gpt-5-nano` não estiver liberado na chave: cair para `gpt-4o-mini` (mesma família de API, sem restrição de `temperature`) e **registrar o desvio no README**, já que o enunciado nomeia `gpt-5-nano`. Ordem de tentativa: `gpt-5-nano` → `gpt-5-mini` → `gpt-4o-mini`. |

---

## 6. Milestones

Sequenciais — cada uma só começa com a anterior fechada.

### M0 — Ambiente ✅ (2026-08-15)
Sem código. Objetivo: conseguir rodar Python e falar com o Postgres. **Começou corrigindo B1–B3.**

- [x] **B1+B2** — `docker-compose.yml`: mapeado `"55432:5432"`, URL do bootstrap devolvida para a porta **interna** 5432
- [x] Validado: `docker compose config` → OK
- [x] **B3** — `.env`: `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/rag`
- [x] **B5** — bug de argv no bootstrap (ver abaixo) — corrigido
- [x] `python3.12 -m venv venv` → Python 3.12.13
- [x] `pip install -r requirements.txt` → 74 pacotes, versões conforme pinadas
- [x] `docker compose up -d` → `postgres_rag` healthy, PostgreSQL 17.11
- [x] **Check da extensão**: `\dx` lista `vector` **0.8.6**
- [x] `OPENAI_CHAT_MODEL='gpt-5-nano'` no `.env` e no `.env.example` (D7)
- [x] Conexão ponta a ponta pelo Python: driver `psycopg` confirmado via SQLAlchemy

**DoD atingida.** Ambiente pronto para a M1.

#### B5 — bug de argv no `bootstrap_vector_ext` (achado durante a execução)

O `\dx` não listava `vector` **mesmo com o container saindo com código 0** e log vazio. Causa real:

```yaml
entrypoint: ["/bin/sh", "-c"]
command: >
  PGPASSWORD=postgres
  psql "postgresql://..." -v ON_ERROR_STOP=1
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

O compose faz *word-splitting* dessa string e produz **7 argumentos**:

```
command:
  - PGPASSWORD=postgres
  - psql
  - postgresql://postgres:postgres@postgres:5432/rag
  - -v
  - ON_ERROR_STOP=1
  - -c
  - CREATE EXTENSION IF NOT EXISTS vector;
```

`sh -c` executa **apenas o primeiro** argumento como script — ou seja, roda `PGPASSWORD=postgres`, uma atribuição de variável que não faz nada, e sai com 0. O `psql` nunca é invocado. A falha é 100% silenciosa.

**Correção:** transformar o `command` em uma lista de **um único elemento** (bloco `|`), para que `sh -c` receba o script inteiro como um argumento só.

> **Isso corrige o diagnóstico do R2.** O bug existe no compose original do upstream e não é race condition — é argv splitting. `docker compose restart bootstrap_vector_ext` (o contorno sugerido pelo PR #6) **nunca resolveria**, porque o comando estava malformado, não atrasado. O `langchain-postgres` 0.0.15 provavelmente mascarava isso ao criar a extensão sozinho na M2, o que explica por que tanta gente entregou sem notar.

---

### M1 — Config + Providers ✅ (2026-08-15)
Primeiro código. As duas peças que sustentam o DIP.

- [x] `src/config.py` — `load_dotenv()`, constantes de env, `require_env(*keys)` e `resolve_pdf_path()`
- [x] `src/providers.py` — `get_embeddings()` e `get_llm()`; **único** módulo que importa `langchain_openai`
- [x] `src/store.py` — `get_vector_store()` com os 4 kwargs do padrão do professor
- [x] `.env.example` com a variável de chat model — feito na M0 (D7)

**DoD atingida:**

| Verificação | Resultado |
|---|---|
| `get_vector_store()` conecta | ✅ `PGVector`, coleção `desafio_rag` |
| Tabelas criadas | ✅ `langchain_pg_collection`, `langchain_pg_embedding` |
| `resolve_pdf_path()` | ✅ resolve para caminho absoluto (B4 fechado) |
| `get_embeddings()` | ✅ `text-embedding-3-small`, **1536 dimensões** |
| `get_llm()` | ✅ `gpt-5-nano` responde, conteúdo não-vazio |

**Antecipações em relação ao plano** (feitas por serem baratas e reduzirem risco à frente):

- **B4 resolvido aqui**, não na M2: `resolve_pdf_path()` mora em `config.py` porque é resolução de configuração. Aceita caminho absoluto e resolve relativo contra `BASE_DIR`, com erro claro se o arquivo não existir.
- **D12 resolvida aqui**, não na M3 — ver abaixo.

#### D12 e D17 — fechadas antecipadamente

Como os providers já estavam prontos, testar custou uma chamada mínima à API:

- **D12(a) `temperature=0.3` → aceito** por `gpt-5-nano`. A preocupação de que a família gpt-5 exigisse `temperature=1` **não se confirmou**. Fica `0.3`, sem fallback necessário.
- **D12(b) resposta vazia → não ocorreu.** Sinal bom, mas o teste foi um prompt curto; a M3 ainda valida com o prompt real (~2,5k tokens de contexto).
- **D17 plano B de modelo → não é necessário.** `gpt-5-nano` está liberado na chave. Fica registrado apenas como contingência.

---

### M2.0 — Spike de extração do PDF ✅ (2026-08-15) 🔬
**Gate de arquitetura (E6). APROVADO** — a extração preserva a linha da tabela.

- [x] `PyPDFLoader(...).load()` executado e `page_content` inspecionado
- [x] Extração confirmada **row-major**

```
Nome da empresa Faturamento Ano de fundação
Alfa Agronegócio Indústria R$ 85.675.568,77 1931
Alfa Ambiental Participações R$ 5.774.383,30 2021
Alfa Energia Holding R$ 858.537,02 1971
```

| Medição | Valor |
|---|---|
| Páginas | 34 |
| Caracteres totais | 45.217 |
| Linhas | 1.002 (1.001 empresas + cabeçalho) |
| Caracteres por página | 527 – 1.395 |
| `creator` do PDF | `Google Sheets` |

**Achado colateral:** o cabeçalho `Nome da empresa Faturamento Ano de fundação` aparece **uma única vez**, na página 1. Chunks das outras 33 páginas não têm rótulo de coluna — o LLM precisa inferir pelo formato (`R$` = faturamento, 4 dígitos = ano). Na prática o formato é autoexplicativo; monitorar na M5.

**Por que era um gate:** se o pypdf emitisse coluna-a-coluna, nome e faturamento se separariam e **a abordagem inteira morreria** — nenhum chunk conteria o par pergunta/resposta. A hipótese row-major, levantada da decodificação bruta dos streams, se confirmou.

---

### M2 — Ingestão ✅ (2026-08-15)

- [x] `src/ingest.py` — `ingest_pdf()`: load → split (1000/150) → higiene de metadata → ids `doc-{i}` → `add_documents`
- [x] `PDF_PATH` resolvido via `config.resolve_pdf_path()` (B4, feito na M1)
- [x] Feedback no terminal: páginas, chunks, confirmação de gravação
- [x] `python src/ingest.py` executado
- [x] Comando de limpeza (D16) documentado no docstring do módulo

**DoD atingida:**

| Verificação | Resultado |
|---|---|
| Chunks gerados | **67** (estimativa do plano era 55–65 — próximo) |
| `count(*)` em `langchain_pg_embedding` | 67 |
| Idempotência (D6) | ✅ reexecutado: 67 → **67**, sem duplicar |

#### Teste antecipado de retrieval (E1/R9)

Como a ingestão já estava no banco, valia medir o **risco central do projeto** antes da M3:

| Pergunta | Distância top-1 | Posição do chunk correto |
|---|---|---|
| `Qual o faturamento da Empresa SuperTechIABrazil?` | 0.450 | **2** |
| `Qual o faturamento da Alfa Energia Holding?` | 0.256 | **1** |
| `Qual é a capital da França?` | 0.778 | — (não existe) |

**R9 (diluição de embedding) rebaixado de Média para Baixa.** O chunk correto aparece no topo, não na cauda do `k=10`. Bônus: perguntas fora de contexto têm distância visivelmente maior (0.778 vs 0.256/0.450) — o que **confirma** que a D15 está certa em não usar threshold, já que o sinal existe mas o prompt dá conta sozinho.

---

### M3 — Busca e chain ✅ (2026-08-15)
A parte sem referência para copiar (§3.1).

- [x] `src/search.py` — `search_prompt(question=None)` devolvendo a chain LCEL de §4.3
- [x] Modo duplo conforme D14
- [x] **E3** — tuplas `(documento, distância)` desempacotadas
- [x] `PROMPT_TEMPLATE` **intocado** — verificado por diff contra `82d86ce:src/search.py`
- [x] D12 já fechada na M1

**DoD atingida:**

| Verificação | Resultado |
|---|---|
| `PROMPT_TEMPLATE` idêntico ao upstream | ✅ comparação programática, `True` |
| Variáveis resolvidas pelo template | ✅ `['contexto', 'pergunta']` |
| Modo fábrica (`search_prompt()`) | ✅ `RunnableSequence`, truthy |
| `Qual o faturamento da Empresa SuperTechIABrazil?` | ✅ `R$ 10.000.000,00` |
| `Qual é a capital da França?` | ✅ frase de recusa **literal** |
| Modo direto (D14) — `ano de fundação da Alfa Energia Holding` | ✅ `1971` (correto, e já é da família colidente do E7) |

**Nota de implementação:** `search_prompt()` captura falhas de inicialização e devolve `None`, imprimindo o erro. Isso torna vivo o `if not chain:` que já vinha escrito no `chat.py` do skeleton — sem isso, aquele early-return seria código morto.

---

### M4 — CLI ⬜

- [ ] `src/chat.py` — loop de `input()` preservando `main()` e o early-return do stub
- [ ] Formato de saída conforme o enunciado (`PERGUNTA:` / `RESPOSTA:`)
- [ ] Saída limpa: comando de sair (`sair`/`exit`), `Ctrl+C` e `Ctrl+D` sem stacktrace
- [ ] Tratar pergunta vazia

**DoD:** `python src/chat.py` roda a sessão completa do exemplo do enunciado, incluindo pergunta fora de contexto.

---

### M5 — Validação ⬜

- [ ] Rodar as 5 perguntas-canário de §2.4
- [ ] **Conferir os valores numéricos contra o PDF real** (o gabarito de §2.4 veio de terceiros)
- [ ] Testar 3–5 empresas adicionais de páginas diferentes (início, meio, fim) — valida que a fragmentação da tabela não cria pontos cegos
- [ ] **Teste de nomes colidentes (E1/E7)** — escolher 2–3 famílias de nome quase idêntico (ex.: `Alfa Energia Holding` / `Alfa Energia S A` / `Alfa Energia Indústria`) e conferir **o valor exato de cada uma** contra o PDF. É o modo de falha mais perigoso: a resposta parece certa e está errada
- [ ] Testar pergunta agregada ("quantas empresas existem?") e confirmar que **recusa** em vez de alucinar
- [ ] Teste de ambiente limpo: `docker compose down -v && docker compose up -d` → ingest → chat

**DoD:** 100% das canárias corretas; **zero troca de valor entre empresas de nome parecido**; nenhuma alucinação nas perguntas fora de contexto.

> Se o teste de nomes colidentes falhar, é sinal de **diluição de embedding** (E1) — o chunk certo não entrou no top-10. Diagnóstico antes de qualquer mudança: imprimir os 10 chunks recuperados e verificar se a linha da empresa está entre eles. Se estiver e o LLM errou → problema de prompt/atenção. Se não estiver → problema de retrieval, e aí a conversa é sobre desviar da spec (o que exige registrar no README).

---

### M6 — Entrega ⬜

- [ ] `README.md` — pré-requisitos, subir Docker, venv + deps, `.env`, rodar ingestão, rodar chat, exemplos de perguntas
- [ ] Confirmar que `.env` **não** está versionado e que `.env.example` não tem segredo
- [ ] Atualizar `CLAUDE.md` (a seção de execução diz para rodar de dentro de `src/`; `python src/chat.py` a partir da raiz também funciona e é o comando que vamos documentar)
- [ ] Commit + push da branch e abertura do PR para `main`

**DoD:** clone limpo do repositório executa a solução seguindo só o README.

---

## 7. Riscos e pontos de atenção

| # | Risco | Probabilidade | Mitigação |
|---|---|---|---|
| R1 | `gpt-5-nano` rejeita `temperature` | Média | D12 — omitir o parâmetro |
| ~~R2~~ | ~~`type "vector" does not exist` na ingestão (PR #6)~~ | ✅ **Eliminado** | **Materializou-se na M0 e foi corrigido na raiz (B5).** O diagnóstico original (race condition, do PR #6) estava errado: era argv splitting no `command` do compose. Extensão `vector` 0.8.6 verificada instalada |
| R3 | `DATABASE_URL` sem `+psycopg` → falha de conexão | Alta se distraído | D8; validar já na M1 |
| R4 | Linha de empresa partida entre chunks → resposta parcial | Média | `overlap=150` + `k=10` já mitigam; detectar na M5 testando páginas variadas |
| **R9** | **Diluição de embedding (E1)** — cada chunk é a média semântica de ~15–20 empresas sem relação; o chunk certo pode não entrar no top-10 | ~~Média~~ → **Baixa** (medido na M2: chunk correto nas posições 1 e 2) | **Risco central do projeto.** Mitigação: `k=10` sobre ~60 chunks já cobre 1/6 do documento. Evidência tranquilizadora: entregas de alunos acertam as canárias com exatamente 1000/150/k=10. Detecção na M5 |
| **R10** | **Resposta trocada entre empresas de nome parecido (E7)** | Média-alta | Pior que errar: a resposta *parece* correta. Teste dedicado na M5 |
| **R11** | Vetores órfãos após mudança de chunking (E2) | Média | D16 — dropar coleção antes de re-ingerir |
| **R12** | `gpt-5-nano` indisponível no tier da chave ou devolvendo conteúdo vazio (E5) | Média | D17 (fallback de modelo) + D12(b) |
| **R13** | Follow-up conversacional não funciona (E8) — `PROMPT_TEMPLATE` não tem histórico | Certa | **Não-goal explícito.** Cada pergunta é independente. Documentar no README para não parecer defeito |
| R5 | Modelo alucina em pergunta agregada em vez de recusar | Média | `PROMPT_TEMPLATE` já tem 3 few-shots de recusa; se falhar, é sinal de que a chain está injetando `{contexto}` errado — **não** editar o template |
| R6 | Re-ingestão duplicando vetores | Baixa | D6 (ids determinísticos) |
| R7 | Custo de API | Desprezível | ~60 embeddings na ingestão + ~2,5k tokens por pergunta |
| R8 | Gabarito de §2.4 vir de terceiros e estar errado | Baixa | M5 confere contra o PDF |

---

## 8. Pendências — respondidas

| # | Pendência | Resposta (2026-08-15) |
|---|---|---|
| 1 | `OPENAI_API_KEY` válida para o `.env` | ✅ **Adicionada** |
| 2 | A plataforma tem critérios de avaliação fora do briefing? | ✅ **Não tem** — o briefing colado é a spec completa. §2.2 deixa de ser incerteza |
| 3 | D12 — `temperature` | ✅ **Começar em `0.3`.** Se a API recusar (família gpt-5 costuma exigir `1`), **omitir o parâmetro** — ver D12 |

**Nenhuma pendência aberta.** O único gate remanescente é a **M2.0**: se o spike de extração falhar, paramos e replanejamos a M2 antes de seguir.

---

## 9. Histórico de revisões

| Data | O que mudou |
|---|---|
| 2026-08-15 | Versão inicial: avaliação do repo, do enunciado e dos dois repositórios de referência; arquitetura; D1–D12; M0–M6 |
| 2026-08-15 | D1 fechada (OpenAI); D9 descartada por consequência |
| 2026-08-15 | **Revalidação.** 4 bloqueadores (B1–B4) e 8 edge cases (E1–E8). Novas decisões D13–D17; D6 e D12 revisadas; nova milestone M2.0 (spike de extração); M0 e M5 endurecidas; riscos R9–R13. Pendências §8 respondidas |
| 2026-08-15 | **M0 executada e concluída.** B1–B3 corrigidos. Novo achado **B5** (argv splitting no bootstrap do compose) — bug do upstream, corrigido na raiz; R2 eliminado e seu diagnóstico original refutado |
| 2026-08-15 | **M1 executada e concluída.** `config.py`, `providers.py`, `store.py`. B4 resolvido antecipadamente em `config.resolve_pdf_path()`; **D12 e D17 fechadas antes da M3** (temperature 0.3 aceito, `gpt-5-nano` disponível) |
| 2026-08-15 | **M2.0 (gate) aprovada** — extração row-major confirmada; gabarito das canárias validado contra o PDF. **M2 concluída** — 67 chunks, idempotência confirmada, R9 rebaixado para Baixa |
