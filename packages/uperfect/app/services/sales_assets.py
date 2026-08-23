"""Validated, local-only response assets for friendly U.Perfect sales replies."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_DIRECTORY = PROJECT_ROOT / "assets" / "chatbot"
SALES_ASSET_PATH = ASSET_DIRECTORY / "sales_response_assets.json"
MANIFEST_PATH = ASSET_DIRECTORY / "asset-manifest.json"
SUPPORTED_LANGUAGES = {"th", "en"}
REQUIRED_INTENTS = {
    "greeting",
    "product_lookup",
    "ingredients",
    "price",
    "delivery",
    "buy",
    "payment",
    "address",
    "objection",
    "fallback",
    "takeover",
}


class SalesAssetError(ValueError):
    """Raised when a response asset would be unsafe or incomplete."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SalesAssetError(f"cannot load sales asset file: {path}") from error
    if not isinstance(value, dict):
        raise SalesAssetError(f"sales asset file must contain an object: {path}")
    return value


def _validate_languages(values: Mapping[str, Any], label: str) -> None:
    if set(values) != SUPPORTED_LANGUAGES:
        raise SalesAssetError(f"{label} must define both th and en")


def _validate_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if manifest.get("version") != "1.0.0" or manifest.get("policy") != "local_product_media_only":
        raise SalesAssetError("asset manifest version or policy is invalid")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise SalesAssetError("asset manifest must contain items")

    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise SalesAssetError("asset manifest item must be an object")
        asset_id = item.get("asset_id")
        path_value = item.get("path")
        if not isinstance(asset_id, str) or not asset_id:
            raise SalesAssetError("asset manifest item is missing asset_id")
        if asset_id in indexed:
            raise SalesAssetError(f"duplicate asset id: {asset_id}")
        if not isinstance(path_value, str) or path_value.startswith(("http://", "https://")):
            raise SalesAssetError(f"asset must be a local relative path: {asset_id}")
        path = (PROJECT_ROOT / path_value).resolve()
        if PROJECT_ROOT not in path.parents or not path.is_file():
            raise SalesAssetError(f"asset file is missing: {path_value}")
        if item.get("language") not in SUPPORTED_LANGUAGES:
            raise SalesAssetError(f"asset language is invalid: {asset_id}")
        indexed[asset_id] = item
    return indexed


def _validate_pack(pack: dict[str, Any], manifest: dict[str, dict[str, Any]]) -> None:
    if pack.get("version") != "1.0.0":
        raise SalesAssetError("unsupported sales asset version")
    if set(pack.get("languages", [])) != SUPPORTED_LANGUAGES:
        raise SalesAssetError("sales assets must support th and en")
    intents = pack.get("intents")
    if not isinstance(intents, dict) or not REQUIRED_INTENTS <= set(intents):
        raise SalesAssetError("sales assets are missing a required intent")
    for intent_id in REQUIRED_INTENTS:
        intent = intents[intent_id]
        if not isinstance(intent, dict):
            raise SalesAssetError(f"intent must be an object: {intent_id}")
        keywords = intent.get("keywords")
        replies = intent.get("replies")
        if not isinstance(keywords, dict) or not isinstance(replies, dict):
            raise SalesAssetError(f"intent is missing keywords or replies: {intent_id}")
        _validate_languages(keywords, f"keywords for {intent_id}")
        _validate_languages(replies, f"replies for {intent_id}")
        if not all(isinstance(values, list) and values for values in keywords.values()):
            raise SalesAssetError(f"intent keywords cannot be empty: {intent_id}")
        if not all(isinstance(value, str) and value.strip() for value in replies.values()):
            raise SalesAssetError(f"intent replies cannot be empty: {intent_id}")

    objections = pack.get("objections")
    if not isinstance(objections, dict) or not objections:
        raise SalesAssetError("sales assets must define objection replies")
    for objection_id, objection in objections.items():
        if not isinstance(objection, dict):
            raise SalesAssetError(f"objection must be an object: {objection_id}")
        _validate_languages(objection.get("keywords", {}), f"objection keywords for {objection_id}")
        _validate_languages(objection.get("replies", {}), f"objection replies for {objection_id}")

    products = pack.get("products")
    if not isinstance(products, dict) or not products:
        raise SalesAssetError("sales assets must define products")
    for product_id, product in products.items():
        if not isinstance(product, dict):
            raise SalesAssetError(f"product asset must be an object: {product_id}")
        if product.get("close_mode") not in {"catalog_review", "admin_review"}:
            raise SalesAssetError(f"invalid close mode: {product_id}")
        asset_ids = product.get("asset_ids", [])
        if not isinstance(asset_ids, list) or not asset_ids:
            raise SalesAssetError(f"product asset has no media: {product_id}")
        for asset_id in asset_ids:
            if asset_id not in manifest:
                raise SalesAssetError(f"unknown media asset {asset_id} for {product_id}")
            if manifest[asset_id].get("product_id") != product_id:
                raise SalesAssetError(f"media asset product mismatch: {asset_id}")
        _validate_languages(product.get("selling_points", {}), f"selling points for {product_id}")


@lru_cache(maxsize=1)
def load_sales_assets() -> dict[str, Any]:
    """Load and validate the response pack once per process."""

    pack = _read_json(SALES_ASSET_PATH)
    manifest = _read_json(MANIFEST_PATH)
    indexed_manifest = _validate_manifest(manifest)
    _validate_pack(pack, indexed_manifest)
    pack["asset_manifest"] = manifest
    pack["asset_index"] = indexed_manifest
    return pack


def language_for_text(text: str, default: str = "th") -> str:
    """Prefer Thai when Thai characters are present, otherwise use English."""

    if re.search(r"[\u0e00-\u0e7f]", text or ""):
        return "th"
    return default if default in SUPPORTED_LANGUAGES else "en"


def render_asset(template: str, values: Mapping[str, object]) -> str:
    """Render only known double-brace placeholders; leave no template syntax behind."""

    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return re.sub(r"\{\{[a-zA-Z0-9_]+\}\}", "", rendered).strip()


def public_sales_assets() -> dict[str, Any]:
    """Return the secret-free payload intended for the dashboard API."""

    pack = load_sales_assets()
    products: dict[str, Any] = {}
    for product_id, item in pack["products"].items():
        products[product_id] = {
            key: value for key, value in item.items() if key != "asset_ids"
        }
        products[product_id]["assets"] = [pack["asset_index"][asset_id] for asset_id in item["asset_ids"]]
    return {
        "version": pack["version"],
        "languages": pack["languages"],
        "default_language": pack["default_language"],
        "intents": pack["intents"],
        "objections": pack["objections"],
        "products": products,
        "safety": pack["safety"],
    }
