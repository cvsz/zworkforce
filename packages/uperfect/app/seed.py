"""Merchant-provided U.Perfect seed facts used by local mode."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal

from app.schemas import Ingredient, Promotion, Product
from app.settings import DEFAULT_WORKSPACE_SETTINGS


SERUM_INCI = (
    "DEIONIZED WATER",
    "GLYCERIN",
    "NIACINAMIDE",
    "HAMAMELIS VIRGINIANA LEAF EXTRACT",
    "CARBOMER",
    "GLYCYRRHIZA GLABRA ROOT EXTRACT",
    "ANTHEMIS NOBILIS FLOWER EXTRACT",
    "SODIUM HYALURONATE",
    "PHENOXYETHANOL",
    "FRAGRANCE",
    "ASCORBIC ACID",
    "TOCOPHEROL",
    "PANTHENOL",
    "BUTYLENE GLYCOL",
    "BIOTIN",
    "ETHYLHEXYLGLYCERIN",
    "DISODIUM EDTA",
    "POLYSORBATE 20",
    "1,2-HEXANEDIOL",
    "FOLIC ACID",
    "RETINYL PALMITATE",
    "PYRIDOXINE HCL",
    "CI 15985",
    "ARACHIS HYPOGAEA OIL",
)


SERUM_INGREDIENTS = (
    Ingredient("Niacinamide", "วิตามินบี 3; merchant copy ระบุว่าช่วยดูแลสีผิวให้สม่ำเสมอและเสริมเกราะผิว", 1),
    Ingredient("Ascorbic acid", "วิตามินซีบริสุทธิ์; merchant copy ระบุว่าเป็นสารต้านอนุมูลอิสระและช่วยดูแลผิวหมองคล้ำ", 2),
    Ingredient("Tocopherol", "วิตามินอี; merchant copy ระบุว่าช่วยต้านอนุมูลอิสระและช่วยคงความชุ่มชื้น", 3),
    Ingredient("Panthenol", "วิตามินบี 5; merchant copy ระบุว่าช่วยปลอบประโลมและเติมความชุ่มชื้น", 4),
    Ingredient("Sodium Hyaluronate", "รูปแบบของไฮยาลูรอเนต; merchant copy ระบุว่าช่วยเติมน้ำให้ผิว", 5),
    Ingredient("Witch hazel", "สารสกัด Hamamelis; merchant copy ระบุว่าช่วยดูแลความมันและความรู้สึกระคายเคือง", 6),
    Ingredient("Chamomile Extract", "สารสกัดดอกคาโมมายล์; merchant copy ระบุว่าช่วยปลอบประโลมผิว", 7),
    Ingredient("Licorice Extract", "สารสกัดรากชะเอมเทศ; merchant copy ระบุว่าช่วยดูแลรอยคล้ำและสีผิว", 8),
)


PRODUCTS = (
    Product(
        id="LOE_VITC_SERUM",
        name="VIT C AURA SERUM เลอ บาย ยู เพอร์เฟค วิต ซี ออร่า เซรั่ม",
        size="200 มิลลิลิตร",
        price_thb=Decimal("98.00"),
        aliases=(
            "วิตซีโลเอ้",
            "วิตซี โลเอ้",
            "loe vit c",
            "vit c aura serum",
            "เซรั่มวิตซี",
            "บอดี้เซรั่ม",
            "วิตามินซีบอดี้เซรั่ม",
            "เลอ บาย ยู เพอร์เฟค",
        ),
        ingredients=SERUM_INGREDIENTS,
        promotions=(
            Promotion(2, Decimal("169.00"), "โปร 2 ชิ้น", Decimal("378.00"), True),
        ),
        description="ผลิตภัณฑ์บำรุงผิวกายจาก Loe by U.PERFECT; ข้อมูลราคาและโปรโมชันมาจาก execution brief และควรตรวจยืนยันก่อนใช้งานจริง",
        seller="U Perfect นายแม่ปุ๊กกี้",
        source_urls=(
            "https://shop.tiktok.com/th/pdp/1736533886654383714",
            "https://shop.tiktok.com/th/pdp/1736534222483654242",
        ),
        source_listing_ids=("1736533886654383714", "1736534222483654242"),
        stock=500,
        usage="ใช้ทาบำรุงผิวกาย",
        warning="หากใช้แล้วมีอาการระคายเคืองควรหยุดใช้และปรึกษาแพทย์",
        inci=SERUM_INCI,
    ),
    Product(
        id="MALA_CHILI_OIL",
        name="น้ำพริกเสือร้องไห้ 1 กระปุก 200 กรัม",
        size="200 กรัม",
        price_thb=None,
        aliases=(
            "น้ำพริกเสือร้องไห้",
            "พริกน้ำมันรำข้าว",
            "mala chili oil",
            "น้ำพริกมาล่า",
            "พริกน้ำมัน",
        ),
        description="พริกน้ำมันรำข้าวใส่ถั่วลายเสือ สูตรต้นตำรับ; ทานกับอะไรก็อร่อย และไม่มีส่วนประกอบของเนื้อสัตว์",
        seller="U Perfect นายแม่ปุ๊กกี้",
        source_urls=("https://shop.tiktok.com/th/pdp/1736721811552831074",),
        source_listing_ids=("1736721811552831074",),
        stock=100,
        allergen_warning="มีส่วนผสมของถั่ว ผู้แพ้อาหารควรหลีกเลี่ยง",
        warning="เปิดแล้วควรปิดฝาให้สนิท และเก็บในที่แห้ง",
    ),
)


def seed_database(connection: sqlite3.Connection) -> None:
    """Insert only facts supplied by the merchant brief, idempotently."""

    for product in PRODUCTS:
        connection.execute(
            """
            INSERT INTO products
              (id, name, size, price_thb, description, seller, merchant_provided,
               available, stock, usage, warning, allergen_warning)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name=excluded.name, size=excluded.size, price_thb=excluded.price_thb,
              description=excluded.description, seller=excluded.seller,
              merchant_provided=excluded.merchant_provided, available=excluded.available,
              stock=excluded.stock, usage=excluded.usage, warning=excluded.warning,
              allergen_warning=excluded.allergen_warning
            """,
            (
                product.id,
                product.name,
                product.size,
                product.price_thb,
                product.description,
                product.seller,
                1 if product.available else 0,
                product.stock,
                product.usage,
                product.warning,
                product.allergen_warning,
            ),
        )
        for position, ingredient in enumerate(product.ingredients, 1):
            connection.execute(
                """
                INSERT INTO ingredients(product_id, name, benefit_copy, position)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(product_id, name) DO UPDATE SET
                  benefit_copy=excluded.benefit_copy, position=excluded.position
                """,
                (product.id, ingredient.name, ingredient.benefit_copy, position),
            )
        for position, inci_name in enumerate(product.inci, 1):
            connection.execute(
                """
                INSERT INTO product_inci(product_id, name, position)
                VALUES (?, ?, ?)
                ON CONFLICT(product_id, name) DO UPDATE SET position=excluded.position
                """,
                (product.id, inci_name, position),
            )
        for position, alias in enumerate(product.aliases, 1):
            connection.execute(
                """
                INSERT INTO product_keywords(product_id, keyword, category, position)
                VALUES (?, ?, 'alias', ?)
                ON CONFLICT(product_id, keyword) DO UPDATE SET position=excluded.position
                """,
                (product.id, alias, position),
            )
        for promo in product.promotions:
            connection.execute(
                """
                INSERT INTO promotions(product_id, minimum_quantity, bundle_price_thb,
                  original_price_thb, label, shipping_free)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, minimum_quantity) DO UPDATE SET
                  bundle_price_thb=excluded.bundle_price_thb,
                  original_price_thb=excluded.original_price_thb,
                  label=excluded.label, shipping_free=excluded.shipping_free
                """,
                (
                    product.id,
                    promo.minimum_quantity,
                    promo.bundle_price_thb,
                    promo.original_price_thb,
                    promo.label,
                    1 if promo.shipping_free else 0,
                ),
            )
        for listing_id, source_url in zip(product.source_listing_ids, product.source_urls, strict=True):
            connection.execute(
                """
                INSERT INTO product_sources(product_id, listing_id, source_url)
                VALUES (?, ?, ?)
                ON CONFLICT(listing_id) DO UPDATE SET product_id=excluded.product_id, source_url=excluded.source_url
                """,
                (product.id, listing_id, source_url),
            )

    for provider, path in (
        ("facebook", "/api/webhooks/facebook"),
        ("tiktok", "/api/webhooks/tiktok"),
        ("shopee", "/api/webhooks/shopee"),
        ("line", "notification outbox"),
        ("n8n", "automation webhook"),
        ("gemini", "server-side provider"),
        ("local_ai", "http://192.168.74.130:11434/api/tags"),
    ):
        connection.execute(
            """
            INSERT INTO integrations(provider, status, webhook_path)
            VALUES (?, 'unconfigured', ?)
            ON CONFLICT(provider) DO UPDATE SET webhook_path=excluded.webhook_path
            """,
            (provider, path),
        )

    for key, value in DEFAULT_WORKSPACE_SETTINGS.items():
        connection.execute(
            """
            INSERT INTO workspace_settings(key, value_json, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO NOTHING
            """,
            (key, json.dumps(value, ensure_ascii=False)),
        )
