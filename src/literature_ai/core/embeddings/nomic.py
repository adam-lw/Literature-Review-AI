from typing import Any
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

from literature_ai.core.embeddings.core import EmbeddingModel


class NomicEmbedText(EmbeddingModel):
    """Nomic Embed Text v1.5 served locally by Ollama.

    Runs against Ollama's OpenAI-compatible endpoint, reusing the same
    ``AsyncOpenAI`` client as :class:`OpenAiEmbedding`. Requires a running
    Ollama server with the model pulled::

        ollama pull nomic-embed-text

    Nomic Embed uses task-specific prefixes (``search_document:``,
    ``search_query:``) that must be prepended to the input text; they are not
    added automatically by Ollama. It emits 768-dim vectors.
    """

    def __init__(self, **config: dict[str, Any]):
        load_dotenv()
        base_url = str(config.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
        # Ollama ignores the API key, but the OpenAI client requires a non-empty value.
        self.client = AsyncOpenAI(base_url=base_url, api_key=os.getenv("OLLAMA_API_KEY", "ollama"))
        self.model = str(config.get("model_name", "nomic-embed-text"))
        self.config = config

    @property
    def n_dim(self) -> int:
        return 768

    async def _embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(input=[text], model=self.model)
        return response.data[0].embedding

    async def embed_paper(self, title: str, abstract: str) -> list[float]:
        return await self._embed(f"search_document: {title}\n{abstract}")

    async def embed_query(self, query: str) -> list[float]:
        return await self._embed(f"search_query: {query}")

    async def embed_text(self, text: str) -> list[float]:
        return await self._embed(f"search_document: {text}")
