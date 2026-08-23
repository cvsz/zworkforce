import json
from pathlib import Path


def test_manifest_uses_canonical_product_directories():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "assets/chatbot/asset-manifest.json").read_text(encoding="utf-8"))
    paths = [item["path"] for item in manifest["items"]]

    assert any(path.startswith("assets/suea_rong_hai_mala_chili_oil/") for path in paths)
    assert any(path.startswith("assets/loe_soap/") for path in paths)
    assert all("น้ำพริกเสือร้องไห้" not in path for path in paths)
    assert all(path.split("/", 2)[1].isascii() and " " not in path.split("/", 2)[1] for path in paths)
    assert all((root / path).is_file() for path in paths)


def test_reference_documents_exist_for_canonical_products():
    root = Path(__file__).resolve().parents[1]

    assert (root / "assets/loe_soap/LOE_Charcoal_Mud_Soap_TH.md").is_file()
    assert (root / "assets/loe_soap/LOE_Charcoal_Mud_Soap_EN.md").is_file()
    assert (root / "assets/suea_rong_hai_mala_chili_oil/Suea_Rong_Hai_Mala_Chili_Oil_TH.md").is_file()
    assert (root / "assets/suea_rong_hai_mala_chili_oil/Suea_Rong_Hai_Mala_Chili_Oil_EN.md").is_file()


def test_vit_c_assets_have_one_canonical_directory_and_named_dossiers():
    root = Path(__file__).resolve().parents[1]
    canonical = root / "assets/loe_vit_c_aura_serum"
    legacy_body = root / "assets/loe_vit_c_aura_body_serum"
    manifest = json.loads((root / "assets/chatbot/asset-manifest.json").read_text(encoding="utf-8"))

    assert canonical.is_dir()
    assert not legacy_body.exists()
    assert (canonical / "Loe_Vit_C_Aura_Serum_Promo_TH.md").is_file()
    assert (canonical / "Loe_Vit_C_Aura_Serum_Promo_EN.md").is_file()
    assert (canonical / "body_notes.txt").is_file()

    vit_c_paths = [item["path"] for item in manifest["items"] if "vit_c" in item["path"]]
    assert vit_c_paths
    assert all(path.startswith("assets/loe_vit_c_aura_serum/") for path in vit_c_paths)


def test_sales_response_asset_ids_resolve_through_the_single_manifest():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "assets/chatbot/asset-manifest.json").read_text(encoding="utf-8"))
    pack = json.loads((root / "assets/chatbot/sales_response_assets.json").read_text(encoding="utf-8"))
    indexed = {item["asset_id"]: item["path"] for item in manifest["items"]}

    for product in pack["products"].values():
        for asset_id in product["asset_ids"]:
            assert asset_id in indexed
            assert (root / indexed[asset_id]).is_file()
