from enum import Enum

from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    ymin: int = Field(..., description="Top boundary coordinate normalized to an integer between 0 and 1000")
    xmin: int = Field(..., description="Left boundary coordinate normalized to an integer between 0 and 1000")
    ymax: int = Field(..., description="Bottom boundary coordinate normalized to an integer between 0 and 1000")
    xmax: int = Field(..., description="Right boundary coordinate normalized to an integer between 0 and 1000")


class ExtractionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class DocumentFields(BaseModel):
    is_required: bool = Field(
        default=False,
        description="Mark if field is required to have value or nullable"
    )
    field: str = Field(
        ...,
        description="Field to extract in the document. eg.: first_name",
    )
    bounding_box: BoundingBox = Field(
        0, description="Bounding box coordinates of the field. eg.: [485, 231, 654, 272]"
    )
    
    
class AgentExtractedDocumentMetadata(BaseModel):
    document_name: str = Field(
        ...,
        description="Batch documents name. eg: National ID",
    ) # 1 name per batch
    fields: list[DocumentFields] = Field(
        description="Extracted fields from document under ID"
    )
    file_name: str = Field(
        ...,
        description="Complete document file name. Examples: national-id.pdf, mypsa.jpg",
    )
    confidence_score: float = Field(
        0.10,
        description="Agent provided confidence score from 1-100. Examples: 0.84, 0.92, 0.99",
    )
    
    
class AgentExtractedSchemaResponse(AgentExtractedDocumentMetadata):
    id: str
    status: ExtractionStatus = ExtractionStatus.SUCCESS
    error: str | None = None  # only populated on failure

