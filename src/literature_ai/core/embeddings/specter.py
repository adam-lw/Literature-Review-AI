from typing import Any
from transformers import AutoTokenizer, AutoModel
from adapters import AutoAdapterModel
import torch

from literature_ai.core.embeddings.core import EmbeddingModel


class SpecterV2Embedding(EmbeddingModel):
    def __init__(self, **config: dict[str, Any]):
        self.tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")
        self.model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
        self.model.load_adapter("allenai/specter2", source="hf", load_as="proximity", set_active=False)
        self.model.load_adapter("allenai/specter2_adhoc_query", source="hf", load_as="adhoc_query", set_active=False)
        self.config = config

    @property
    def n_dim(self) -> int:
        return 768

    def _run(self, inputs) -> list[float]:
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[0, 0, :].tolist()

    async def embed_paper(self, title: str, abstract: str) -> list[float]:
        self.model.set_active_adapters("proximity")
        text = f"{title}{self.tokenizer.sep_token}{abstract}"
        inputs = self.tokenizer(text, padding=True, truncation=True, max_length=512, return_tensors="pt")
        return self._run(inputs)

    async def embed_query(self, query: str) -> list[float]:
        self.model.set_active_adapters("adhoc_query")
        inputs = self.tokenizer(query, padding=True, truncation=True, max_length=512, return_tensors="pt")
        return self._run(inputs)

    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError("SpecterV2Embedding does not support embed_text")


class SpecterV1Embedding(EmbeddingModel):
    def __init__(self, **config: dict[str, Any]):
        self.tokenizer = AutoTokenizer.from_pretrained("allenai/specter")
        self.model = AutoModel.from_pretrained("allenai/specter")
        self.config = config

    @property
    def n_dim(self) -> int:
        return 768

    def _run(self, inputs) -> list[float]:
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[0, 0, :].tolist()

    async def embed_paper(self, title: str, abstract: str) -> list[float]:
        text = f"{title}{self.tokenizer.sep_token}{abstract}"
        inputs = self.tokenizer(text, padding=True, truncation=True, max_length=512, return_tensors="pt")
        return self._run(inputs)

    async def embed_query(self, query: str) -> list[float]:
        inputs = self.tokenizer(query, padding=True, truncation=True, max_length=512, return_tensors="pt")
        return self._run(inputs)

    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError("SpecterV1Embedding does not support embed_text")
