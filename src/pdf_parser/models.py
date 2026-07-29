from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Point(BaseModel):
    x: int
    y: int


class Position(BaseModel):
    points: list[Point]


class DocumentDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    text: str = ""
    position: list[Position] = Field(default_factory=list)
    layout_label: str
    layout_mapped_type: str
    layout_score: float | None = None
    layout_order: float
    layout_reading_index: int
    layout_bbox: list[int]
    layout_fallback_text: str = ""


class SealText(BaseModel):
    text: str
    ocr_confidence: float | None = None
    position: list[Position] = Field(default_factory=list)
    layout_bbox: list[int] = Field(default_factory=list)


class SealDetail(DocumentDetail):
    type: Literal["Seal"] = "Seal"
    layout_label: Literal["seal"] = "seal"
    layout_mapped_type: Literal["Seal"] = "Seal"
    seal_id: str
    seal_index: int
    reference_token: str
    seal_region_bbox: list[int] = Field(default_factory=list)
    coordinate_space: Literal["page_pixels_top_left"] = "page_pixels_top_left"
    texts: list[SealText] = Field(default_factory=list)


class ContentReference(BaseModel):
    token: str
    target_type: Literal["Seal"] = "Seal"
    target_id: str
    start_offset: int
    end_offset: int


class PageResult(BaseModel):
    page_num: int
    document_content: str
    image_width: int
    image_height: int
    document_details: list[SealDetail | DocumentDetail] = Field(default_factory=list)
    content_references: list[ContentReference] = Field(default_factory=list)
    parse_time: float

    @model_validator(mode="after")
    def require_structured_seal_details(self) -> PageResult:
        if any(
            detail.type == "Seal" and not isinstance(detail, SealDetail)
            for detail in self.document_details
        ):
            raise ValueError("type=Seal 的文档元素必须使用 SealDetail")
        return self


class ResultData(BaseModel):
    task_id: str = ""
    file_url: str = ""
    status: int = 4
    message: str = ""
    doc_recognize_result: list[PageResult]
    aigc: dict[str, Any] = Field(
        default_factory=lambda: {
            "Label": "AIGCLabelType.AI_GENERATED",
            "ProcessingTypes": ["ocr"],
        }
    )


class ParseResponse(BaseModel):
    code: str = "success"
    message: str = ""
    tips: str | None = None
    data: ResultData
