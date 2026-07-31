class PdfParserError(RuntimeError):
    """Base exception for user-facing parser failures."""


class InvalidPdfError(PdfParserError):
    """The input PDF cannot be processed."""


class InvalidImageError(PdfParserError):
    """The input image cannot be processed."""


class PaddleXError(PdfParserError):
    """The remote PaddleX service returned an invalid or failed response."""


class VLMError(PdfParserError):
    """The optional VLM service returned an invalid or failed response."""
