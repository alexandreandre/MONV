from utils.text_sanitize import strip_emojis


def test_strip_emojis_removes_pictographs():
    assert strip_emojis("Bonjour 👋") == "Bonjour"
    assert strip_emojis("A ✏️ B") == "A B"


def test_strip_emojis_preserves_punctuation():
    assert strip_emojis("CA : 10 M€ (estim.)") == "CA : 10 M€ (estim.)"
