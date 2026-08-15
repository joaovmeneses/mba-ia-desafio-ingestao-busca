from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from providers import get_llm
from store import get_vector_store

RETRIEVED_CHUNKS = 10

PROMPT_TEMPLATE = """
CONTEXTO:
{contexto}

REGRAS:
- Responda somente com base no CONTEXTO.
- Se a informação não estiver explicitamente no CONTEXTO, responda:
  "Não tenho informações necessárias para responder sua pergunta."
- Nunca invente ou use conhecimento externo.
- Nunca produza opiniões ou interpretações além do que está escrito.

EXEMPLOS DE PERGUNTAS FORA DO CONTEXTO:
Pergunta: "Qual é a capital da França?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Quantos clientes temos em 2024?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Você acha isso bom ou ruim?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

PERGUNTA DO USUÁRIO:
{pergunta}

RESPONDA A "PERGUNTA DO USUÁRIO"
"""

def build_chain():
    store = get_vector_store()
    llm = get_llm()

    def retrieve_context(question: str) -> str:
        matches = store.similarity_search_with_score(question, k=RETRIEVED_CHUNKS)
        return "\n\n".join(document.page_content for document, _distance in matches)

    return (
        {
            "contexto": RunnableLambda(retrieve_context),
            "pergunta": RunnablePassthrough(),
        }
        | PromptTemplate.from_template(PROMPT_TEMPLATE)
        | llm
        | StrOutputParser()
    )


def search_prompt(question=None):
    try:
        chain = build_chain()
    except Exception as error:
        print(f"Erro ao inicializar a busca: {error}")
        return None

    return chain.invoke(question) if question else chain