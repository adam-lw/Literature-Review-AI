from abc import ABC, abstractmethod
from typing import Any
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

OPENAI_MODELS = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
]


class EmbeddingModel(ABC):
    def __init__(self, **config):
        self.config = config

    @property
    @abstractmethod
    def n_dim(self) -> int: ...

    @property
    def version(self) -> str | None:
        return None

    @abstractmethod
    async def embed_paper(self, title: str, abstract: str) -> list[float]: ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]: ...

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]: ...


class OpenAiEmbedding(EmbeddingModel):
    def __init__(self, model: str, **config: dict[str, Any]):
        load_dotenv()
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.config = config

    @property
    def n_dim(self) -> int:
        return int(self.config.get("dimensions", 1536))

    async def _embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            input=[text],
            model=self.model,
            dimensions=self.config.get("dimensions", 1536),
        )
        return response.data[0].embedding

    async def embed_paper(self, title: str, abstract: str) -> list[float]:
        return await self._embed(f"{title}: {abstract}")

    async def embed_query(self, query: str) -> list[float]:
        return await self._embed(query)

    async def embed_text(self, text: str) -> list[float]:
        return await self._embed(text)


_MODEL_CACHE: dict[str, EmbeddingModel] = {}


def get_embedding_model(model: str) -> EmbeddingModel:
    if model not in _MODEL_CACHE:
        from literature_ai.core.embeddings.specter import SpecterV1Embedding, SpecterV2Embedding
        from literature_ai.core.embeddings.qwen3 import Qwen3Embedding
        from literature_ai.core.embeddings.bge_m3 import BgeM3Embedding
        from literature_ai.core.embeddings.nomic import NomicEmbedText

        if model in OPENAI_MODELS:
            _MODEL_CACHE[model] = OpenAiEmbedding(model=model)
        elif model == "specter_v2":
            _MODEL_CACHE[model] = SpecterV2Embedding()
        elif model == "specter_v1":
            _MODEL_CACHE[model] = SpecterV1Embedding()
        elif model == "qwen3_embedding_4b":
            _MODEL_CACHE[model] = Qwen3Embedding()
        elif model == "bge_m3":
            _MODEL_CACHE[model] = BgeM3Embedding()
        elif model == "nomic_embed_text":
            _MODEL_CACHE[model] = NomicEmbedText()
        else:
            raise ValueError(f"Embedding model `{model}` not found.")
    return _MODEL_CACHE[model]
