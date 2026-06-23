from abc import ABC, abstractmethod
from typing import Any
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
from transformers import AutoTokenizer, AutoModel
import torch

OPENAI_MODELS = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
]

SPECTER = "specter-v2"


class EmbeddingModel(ABC):
    """
    Abstract base class for embedding models.
    All embedding models should inherit from this class and implement the `call` method.
    """

    def __init__(self, **config):
        self.config = config

    @abstractmethod
    async def call(self, text: str | list[str]) -> list[float]:
        """
        Text to embed with the initialised embedding model
        """
        ...


class SpecterEmbedding(EmbeddingModel):
    """
    Embedding model class for SPECTER v2 from Hugging Face.
    """

    def __init__(self, **config: dict[str, Any]):
        
        self.tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")
        self.model = AutoModel.from_pretrained("allenai/specter2_base")
        self.config = config

    async def call(self, text: str | list[str]) -> list[float]:
        
        if isinstance(text, str):
            text = [text]
        
        inputs = self.tokenizer(text, padding=True, truncation=True, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        embeddings = outputs.last_hidden_state[:, 0, :].tolist()
        return embeddings


class OpenAiEmbedding(EmbeddingModel):
    """
    Embedding model class for OpenAI embedding models.
    """

    def __init__(self, model: str, **config: dict[str, Any]):
        load_dotenv()
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.config = config

    async def call(self, text: str | list[str]) -> list[float]:
        embedding = await (
            self.client.embeddings.create(
                input=[text],
                model=self.model,
                dimensions=self.config.get("dimensions", 1536)
            )
        )
        return [emb.embedding for emb in embedding.data]


def get_embedding_model(model: str) -> EmbeddingModel:
    """
    Factory method for embedding models.
    Given a model name, returns an instance of the corresponding embedding model class.
    """
    if model in OPENAI_MODELS:
        return OpenAiEmbedding(model=model)
    elif model == SPECTER:
        return SpecterEmbedding()
    else:
        raise ValueError(f"Embedding model `{model}` not found.")
