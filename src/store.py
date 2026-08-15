from langchain_postgres import PGVector

from config import DATABASE_URL, PG_VECTOR_COLLECTION_NAME, require_env
from providers import get_embeddings


def get_vector_store() -> PGVector:
    require_env("DATABASE_URL", "PG_VECTOR_COLLECTION_NAME")
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=PG_VECTOR_COLLECTION_NAME,
        connection=DATABASE_URL,
        use_jsonb=True,
    )
