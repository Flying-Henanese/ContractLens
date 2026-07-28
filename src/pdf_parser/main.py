"""FastAPI service entry point."""

from __future__ import annotations

import uvicorn

from pdf_parser.api import app

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8888

__all__ = ["app", "main"]


def main() -> None:
    """Run the FastAPI service with production-safe import semantics."""
    uvicorn.run(
        "pdf_parser.main:app",
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
    )


if __name__ == "__main__":
    main()
