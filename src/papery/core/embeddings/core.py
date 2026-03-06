from abc import ABC, abstractmethod
from typing import Any
from openai import OpenAI
from dotenv import load_dotenv
import os

OPENAI_MODELS = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
]


class EmbeddingModel(ABC):
    """
    Abstract base class for embedding models.
    All embedding models should inherit from this class and implement the `call` method.
    """

    def __init__(self, **config):
        self.config = config

    @abstractmethod
    def call(self, text: str):
        """
        Text to embed with the initialised embedding model
        """
        ...


class OpenAiEmbedding(EmbeddingModel):
    """
    Embedding model class for OpenAI embedding models.
    """

    def __init__(self, model: str, **config: dict[str, Any]):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.config = config

    def call(self, text: str):
        embedding = (
            self.client.embeddings.create(
                input=[text],
                model=self.model,
                dimensions=self.config.get("dimensions", 1536),
            )
            .data[0]
            .embedding
        )

        return embedding


def get_embedding_model(model: str) -> EmbeddingModel:
    """
    Factory method for embedding models.
    Given a model name, returns an instance of the corresponding embedding model class.
    """
    if model in OPENAI_MODELS:
        return OpenAiEmbedding(model=model)
    else:
        raise ValueError(f"Embedding model `{model}` not found.")
