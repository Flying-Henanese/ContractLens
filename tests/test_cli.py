import json

from typer.testing import CliRunner

from pdf_parser.cli import app


class _FakeResult:
    def model_dump(self) -> dict:
        return {"code": "success", "data": {"doc_recognize_result": []}}


def test_parse_defaults_to_output_directory_without_overwriting_input_sibling(
    tmp_path, monkeypatch
):
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"%PDF-test")
    sibling_result = tmp_path / "sample_result.json"
    sibling_result.write_text("user sample", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    async def fake_parse_pdf(*_args, **_kwargs):
        return _FakeResult()

    monkeypatch.setattr("pdf_parser.cli.parse_pdf", fake_parse_pdf)

    result = CliRunner().invoke(app, ["parse", str(source)])

    output = tmp_path / "output" / "sample_result.json"
    assert result.exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["code"] == "success"
    assert sibling_result.read_text(encoding="utf-8") == "user sample"
