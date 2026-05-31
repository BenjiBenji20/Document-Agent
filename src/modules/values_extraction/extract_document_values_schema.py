from typing import Annotated, Any
from uuid import UUID
from pydantic import BaseModel, Field

from src.modules.gcs_operations.direct_gcs_operations_schema import GCSFileObjectMetadata
from src.modules.fields_registration.document_registration_schema import DocumentFields
from src.utils.validators import SafeLabel
from src.agents.schemas.agent_extract_schemas import ExtractionStatus

class DocumentToExtactValues(BaseModel):
    document_id: UUID = Field(
        ...,
        description="Unique identifier for the document type schema reference"
    )
    document_name: SafeLabel = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Document type name. eg.: National ID, Drivers License",
    )
    fields: Annotated[list[DocumentFields], Field(
        ...,
        min_length=1,
        max_length=30,
        description="Dynamic fields to extract in the documents. eg.: [first_name, last_name, date-of-birth]",
    )]
    downloadable_url: str = Field(
        ...,
        description="GCS file URL to download by agent"
    )
    gcs_file_metadata: GCSFileObjectMetadata = Field(
        ...,
        description="File's metadata present in gcs"
    )


class DocumentValueExtractionRequest(BaseModel):
    document_id: UUID = Field(
        ..., 
        description="Unique ID of the registered document schema"
    )
    file_id: UUID = Field(
        ..., 
        description="ID of the uploaded file in GCS"
    )
    file_name: str = Field(
        ..., 
        min_length=1, 
        max_length=255, 
        description="Name of the file, e.g., my_document.pdf"
    )
    file_type: str = Field(
        ..., 
        description="MIME type of the file. eg: image/png, application/pdf"
    )


class ExtractionValueResponse(BaseModel):
    document_id: UUID = Field(
        ..., 
        description="Document type schema ID"
    )
    file_id: UUID = Field(
        ..., 
        description="GCS uploaded file ID"
    )
    document_name: str = Field(
        ..., 
        description="Document type name"
    )
    file_name: str = Field(
        ..., 
        description="Name of the processed file"
    )
    field_values: dict[str, Any] = Field(
        ..., 
        description="Extracted values"
    )
    confidence_score: float = Field(
        ..., 
        description="Extraction confidence score"
    )
    score_reason: str | None = Field(
        default=None, 
        description="Reason for the confidence score"
    )
    status: ExtractionStatus = Field(
        ..., 
        description="Status of extraction"
    )
    error: str | None = Field(
        default=None, 
        description="Error message, if any"
    )