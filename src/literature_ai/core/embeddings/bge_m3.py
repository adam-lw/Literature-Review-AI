from typing import Any
from transformers import AutoTokenizer, AutoModel
import torch
import torch.nn.functional as F

from literature_ai.core.embeddings.core import EmbeddingModel


class BgeM3Embedding(EmbeddingModel):
    """Dense retrieval with BAAI/bge-m3.

    BGE-M3 also exposes sparse and ColBERT (multi-vector) outputs, but this
    implementation returns only the dense CLS embedding to fit the single
    ``list[float]`` contract shared across ``EmbeddingModel`` subclasses.
    """

    def __init__(self, **config: dict[str, Any]):
        model_name = str(config.get("model_name", "BAAI/bge-m3"))
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()
        self.max_length = int(config.get("max_length", 8192))
        self.config = config

    @property
    def n_dim(self) -> int:
        return 1024

    def _embed(self, text: str) -> list[float]:
        inputs = self.tokenizer(
            text, padding=True, truncation=True, max_length=self.max_length, return_tensors="pt"
        )
        with torch.no_grad():
            outputs = self.model(**inputs)
        # BGE-M3 dense embedding is the normalized CLS token hidden state.
        embedding = outputs.last_hidden_state[:, 0]
        embedding = F.normalize(embedding, p=2, dim=1)
        return embedding[0].tolist()

    async def embed_paper(self, title: str, abstract: str) -> list[float]:
        return self._embed(f"{title}\n{abstract}")

    async def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    async def embed_text(self, text: str) -> list[float]:
        return self._embed(text)
