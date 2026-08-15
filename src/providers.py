"""Fábricas do modelo de embeddings e do LLM.

Único ponto do projeto que conhece o provider concreto. `ingest.py` e `search.py`
dependem apenas destas funções, então trocar de provider não afeta nenhum dos dois.
"""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config import OPENAI_CHAT_MODEL, OPENAI_EMBEDDING_MODEL, require_env

# Baixa o suficiente para manter as respostas presas ao contexto recuperado.
TEMPERATURE = 0.3


def get_embeddings():
    """Modelo de embeddings usado tanto na ingestão quanto na busca.

    Os dois lados precisam usar o mesmo modelo: vetores de modelos diferentes não
    são comparáveis e a busca degrada em silêncio.
    """
    require_env("OPENAI_API_KEY")
    return OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)


def get_llm():
    """LLM que redige a resposta final a partir do contexto recuperado."""
    require_env("OPENAI_API_KEY")
    return ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=TEMPERATURE)
