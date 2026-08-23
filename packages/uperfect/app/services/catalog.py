"""Product and keyword memory service."""

from __future__ import annotations

from app.repositories import Repository
from app.schemas import Product


class CatalogService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def list_products(self, query: str | None = None) -> list[Product]:
        return self.repository.list_products(query)

    def get(self, product_id: str) -> Product:
        return self.repository.get_product(product_id)

    def get_optional(self, product_id: str | None) -> Product | None:
        return self.repository.get_product_optional(product_id)

    def find_by_text(self, text: str) -> Product | None:
        normalized = " ".join((text or "").casefold().split())
        if not normalized:
            return None
        matches = self.repository.find_keyword_matches(normalized)
        return max(matches, key=lambda product: len(product.matched_alias), default=None)

    def save(self, product: Product) -> Product:
        return self.repository.save_product(product)
