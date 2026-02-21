from typing import Protocol

class EmbeddingProvider(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]:
        pass