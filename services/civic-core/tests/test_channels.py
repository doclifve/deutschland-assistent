from deutschland_assistent.channels import channels_info, whatsapp_channel


def test_whatsapp_disabled_without_number():
    wa = whatsapp_channel({})
    assert wa.enabled is False and wa.link is None and wa.display_number is None


def test_whatsapp_link_from_formatted_number():
    wa = whatsapp_channel({"WHATSAPP_PUBLIC_NUMBER": "+49 151 2345 6789"})
    assert wa.enabled is True
    assert wa.display_number == "+49 151 2345 6789"
    assert wa.link == "https://wa.me/4915123456789?text=Hallo"


def test_whatsapp_international_prefix_and_greeting():
    wa = whatsapp_channel({"WHATSAPP_PUBLIC_NUMBER": "0049 40 123456", "WHATSAPP_GREETING": "Hallo Assistent"})
    assert wa.link == "https://wa.me/4940123456?text=Hallo%20Assistent"
    assert wa.display_number == "+4940123456"


def test_whatsapp_rejects_national_or_invalid_numbers():
    assert whatsapp_channel({"WHATSAPP_PUBLIC_NUMBER": "0151 23456789"}).enabled is False
    assert whatsapp_channel({"WHATSAPP_PUBLIC_NUMBER": "12345"}).enabled is False


def test_channels_info_shape():
    info = channels_info({"WHATSAPP_PUBLIC_NUMBER": "+4915123456789"}).model_dump()
    assert set(info) == {"whatsapp"}
    assert set(info["whatsapp"]) == {"enabled", "display_number", "link", "greeting"}
