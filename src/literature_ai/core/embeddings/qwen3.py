from typing import Any
from openai import AsyncOpenAI
from dotenv import load_dotenv
import math
import os

from literature_ai.core.embeddings.core import EmbeddingModel

# Qwen3-Embedding is trained with Matryoshka Representation Learning, so the
# leading prefix of each vector is itself a valid (lower-dimensional) embedding
# once re-normalized. We truncate to this many dims by default: it keeps most
# of the quality while staying under pgvector's 2000-dim HNSW index limit and
# cutting storage. Set output_dim=None in config to keep the full 2560 dims.
_DEFAULT_OUTPUT_DIM = 1024

# Qwen3-Embedding expects queries to be wrapped with a one-sentence task
# instruction, while documents are embedded as-is. The instruction is plain
# prepended text — Ollama does not add it automatically. See the model card:
# https://huggingface.co/Qwen/Qwen3-Embedding-4B
_QUERY_INSTRUCTION = "Given a search query, retrieve relevant academic papers that answer the query"


class Qwen3Embedding(EmbeddingModel):
    """Qwen3-Embedding-4B served locally by Ollama.

    Runs against Ollama's OpenAI-compatible endpoint, so it reuses the same
    ``AsyncOpenAI`` client as :class:`OpenAiEmbedding`. Requires a running
    Ollama server with the model pulled::

        ollama pull qwen3-embedding:4b

    The 4B variant emits 2560-dim vectors and fits comfortably in the 16GB of
    an M4 Air. Override ``model_name`` in config for the 0.6B/8B sizes.
    """

    def __init__(self, **config: dict[str, Any]):
        load_dotenv()
        base_url = str(config.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
        # Ollama ignores the API key, but the OpenAI client requires a non-empty value.
        self.client = AsyncOpenAI(base_url=base_url, api_key=os.getenv("OLLAMA_API_KEY", "ollama"))
        self.model = str(config.get("model_name", "qwen3-embedding:4b"))
        self.config = config

    @property
    def n_dim(self) -> int:
        return 2560

    async def _embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(input=[text], model=self.model)
        return response.data[0].embedding

    @staticmethod
    def _format_query(query: str) -> str:
        return f"Instruct: {_QUERY_INSTRUCTION}\nQuery: {query}"

    async def embed_paper(self, title: str, abstract: str) -> list[float]:
        return await self._embed(f"{title}\n{abstract}")

    async def embed_query(self, query: str) -> list[float]:
        return await self._embed(self._format_query(query))

    async def embed_text(self, text: str) -> list[float]:
        return await self._embed(text)
