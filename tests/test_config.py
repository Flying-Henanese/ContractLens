from pdf_parser.config import Settings


def test_layout_detection_settings_can_be_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("PDF_PARSER_USE_LAYOUT_DETECTION", "false")
    monkeypatch.setenv("PDF_PARSER_LAYOUT_THRESHOLD", "0.35")

    settings = Settings(_env_file=None)

    assert settings.use_layout_detection is False
    assert settings.layout_threshold == 0.35
