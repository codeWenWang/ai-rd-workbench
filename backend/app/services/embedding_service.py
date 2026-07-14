from app.config import settings
from app.services.openai_client import get_openai_client


class EmbeddingService:
    def __init__(self):
        self.client = get_openai_client()
        self.model = settings.embedding_model
        self.dimension = settings.embedding_dimension

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimension,
            encoding_format="float",
        )
        return [item.embedding for item in response.data]


embedding_service = EmbeddingService()
