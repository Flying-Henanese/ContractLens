from pdf_parser.config import Settings


def test_vlm_defaults_are_safe_and_use_configurable_endpoint():
    settings = Settings(_env_file=None)

    assert settings.endpoint == "http://192.168.0.67:8880"
    assert settings.vlm_enabled is False
    assert settings.vlm_endpoint == "http://192.168.0.194:8000"
    assert settings.vlm_chat_url == "http://192.168.0.194:8000/v1/chat/completions"
    assert settings.vlm_timeout_seconds == 30
    assert settings.vlm_max_attempts == 5


def test_vlm_settings_can_be_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("PDF_PARSER_VLM_ENABLED", "true")
    monkeypatch.setenv("PDF_PARSER_VLM_ENDPOINT", "http://vlm.internal:9000/api/")
    monkeypatch.setenv("PDF_PARSER_VLM_MODEL", "another-model")
    monkeypatch.setenv("PDF_PARSER_VLM_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("PDF_PARSER_VLM_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("PDF_PARSER_VLM_SEAL_OCR_THRESHOLD", "0.75")

    settings = Settings(_env_file=None)

    assert settings.vlm_enabled is True
    assert settings.vlm_chat_url == "http://vlm.internal:9000/api/v1/chat/completions"
    assert settings.vlm_model == "another-model"
    assert settings.vlm_timeout_seconds == 15
    assert settings.vlm_max_attempts == 3
    assert settings.vlm_seal_ocr_threshold == 0.75
