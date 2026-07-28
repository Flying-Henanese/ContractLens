from pdf_parser.api import app as api_app
from pdf_parser.main import DEFAULT_HOST, DEFAULT_PORT, app, main


def test_main_exports_existing_fastapi_app():
    assert app is api_app
    assert DEFAULT_PORT == 8888


def test_main_starts_uvicorn(monkeypatch):
    observed: dict[str, object] = {}

    def fake_run(application: str, **kwargs):
        observed["application"] = application
        observed.update(kwargs)

    monkeypatch.setattr("pdf_parser.main.uvicorn.run", fake_run)

    main()

    assert observed == {
        "application": "pdf_parser.main:app",
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
    }
