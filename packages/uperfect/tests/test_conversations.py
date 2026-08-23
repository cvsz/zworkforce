from app.schemas import InboundMessage


def test_product_context_is_reused_for_an_ingredient_question(conversations):
    conversations.receive(InboundMessage("facebook", "a1", "สนใจวิตซีโลเอ้"))
    result = conversations.receive(InboundMessage("facebook", "a1", "มีส่วนผสมอะไรบ้าง"))

    assert result.active_product_id == "LOE_VITC_SERUM"
    assert result.intent == "ingredients"
    assert "Niacinamide" in result.reply


def test_unknown_price_is_not_invented_for_mala(conversations):
    result = conversations.receive(InboundMessage("tiktok", "a2", "น้ำพริกเสือร้องไห้ราคาเท่าไร"))

    assert result.active_product_id == "MALA_CHILI_OIL"
    assert result.intent == "price"
    assert "ยังไม่มีราคาที่ยืนยัน" in result.reply


def test_takeover_suppresses_automatic_reply(conversations):
    first = conversations.receive(InboundMessage("shopee", "a3", "สนใจวิตซีโลเอ้"))
    conversations.set_takeover(first.conversation.id, True)
    result = conversations.receive(InboundMessage("shopee", "a3", "ราคาเท่าไร"))

    assert result.automated is False
    assert result.reply is None


def test_serum_price_reply_contains_a_close_sale_cta(conversations):
    result = conversations.receive(InboundMessage("facebook", "a4", "วิตซีโลเอ้มีโปรไหม"))

    assert result.intent == "price"
    assert "169" in result.reply
    assert "รับโปร" in result.reply
    assert "ชำระเงินสำเร็จ" not in result.reply


def test_sensitive_skin_objection_is_careful_and_still_moves_to_checkout(conversations):
    conversations.receive(InboundMessage("facebook", "a5", "สนใจวิตซีโลเอ้"))
    result = conversations.receive(InboundMessage("facebook", "a5", "ผิวแพ้ง่ายใช้ได้ไหม"))

    assert result.intent == "objection"
    assert "ทดสอบการแพ้" in result.reply
    assert "รับโปร" in result.reply


def test_unpriced_product_objection_never_invents_a_close_sale_total(conversations):
    result = conversations.receive(InboundMessage("tiktok", "a6", "น้ำพริกเสือร้องไห้เอา 2 กระปุก"))

    assert result.intent == "buy"
    assert "ยังไม่มีราคาที่ยืนยัน" in result.reply
    assert "บาท" not in result.reply
