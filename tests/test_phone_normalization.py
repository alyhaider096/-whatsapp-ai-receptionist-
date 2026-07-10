from app.routers.settings import _normalize_whatsapp_number


def test_normalize_pakistan_local_mobile_number():
    assert _normalize_whatsapp_number("03030222057") == "923030222057"


def test_normalize_pakistan_mobile_without_zero():
    assert _normalize_whatsapp_number("3030222057") == "923030222057"


def test_normalize_pakistan_international_number():
    assert _normalize_whatsapp_number("+92 303 0222057") == "923030222057"
