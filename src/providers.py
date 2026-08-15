from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config import (
    AI_TEMPERATURE,
    OPENAI_CHAT_MODEL,
    OPENAI_EMBEDDING_MODEL,
    require_env,
)


def get_embeddings() -> OpenAIEmbeddings:
    require_env("OPENAI_API_KEY")
    return OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)


def get_llm() -> ChatOpenAI:
    require_env("OPENAI_API_KEY")
    return ChatOpenAI(model=OPENAI_CHAT_MODEL, temperature=AI_TEMPERATURE)
