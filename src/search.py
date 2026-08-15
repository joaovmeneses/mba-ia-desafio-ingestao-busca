"""Busca no banco vetorial e geração da resposta.

Monta a chain que liga os chunks recuperados ao LLM. O PROMPT_TEMPLATE abaixo é o
contrato do desafio: mantém a resposta presa ao contexto e define a frase exata de
recusa. Não alterar.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from providers import get_llm
from store import get_vector_store

# Quantidade de chunks recuperados por pergunta, conforme o enunciado.
K = 10

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

def search_prompt(question=None):
    """Monta a chain de pergunta e resposta sobre o conteúdo ingerido.

    Sem argumento, devolve a chain para ser reaproveitada a cada pergunta — é assim
    que o `chat.py` usa. Com uma pergunta, já invoca e devolve a resposta em texto.

    Devolve `None` se a inicialização falhar, para o chamador tratar (o `chat.py`
    depende disso).
    """
    try:
        store = get_vector_store()
        llm = get_llm()
    except Exception as erro:
        print(f"Erro ao inicializar a busca: {erro}")
        return None

    def buscar_contexto(pergunta: str) -> str:
        # similarity_search_with_score devolve pares (documento, distância); aqui só
        # o texto importa, mas a API é a exigida pelo enunciado.
        resultados = store.similarity_search_with_score(pergunta, k=K)
        return "\n\n".join(documento.page_content for documento, _distancia in resultados)

    chain = (
        {
            "contexto": RunnableLambda(buscar_contexto),
            "pergunta": RunnablePassthrough(),
        }
        | PromptTemplate.from_template(PROMPT_TEMPLATE)
        | llm
        | StrOutputParser()
    )

    if question:
        return chain.invoke(question)
    return chain