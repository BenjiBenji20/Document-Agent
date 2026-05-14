from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, field_validator, ConfigDict, Field
from src.utils.validators import SafeLabel, FieldName, Honeypot

# =====================
# MANUAL FEATURE MODELS
# =====================
class DocumentFields(BaseModel):
    is_required: bool = Field(
        default=False,
        description="Mark if field is required to have value or nullable"
    )
    field: FieldName = Field(
        ...,
        min_length=1,
        max_length=30, # Cap field count — protects agent prompt size
        description="Field to extract in the document",
        examples=["first_name"],
    )
        
    model_config = ConfigDict(frozen=True)
    

class DocumentRegistrationRequest(BaseModel):
    document_name: SafeLabel = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Document type name",
        examples=["National ID", "Driver's License"],
    )
    fields: Annotated[list[DocumentFields], Field(
        ...,
        min_length=1,
        max_length=30,
        description="Dynamic fields to extract in the documents.",
        examples=[["first_name", "last_name", "date-of-birth"]],
    )]
    honeypot: Honeypot = Field(
        default=None,
        exclude=True, # Never surfaces in serialized output / logs
        description="Anti-bot trap. Must be empty.",
    )

    @field_validator("fields")
    @classmethod
    def validate_fields_entry_uniqueness(cls, fields: list[DocumentFields]):
        seen = set()
        unique_fields = []
        for f in fields:
            if f.field not in seen:
                seen.add(f.field)
                unique_fields.append(f)
        return unique_fields
    
    
# ==============================+
# Internal or Output only schemas
# ===============================
    
class ResponseDetails(BaseModel):
    description: str | None = Field(
        default=None,
        description="Response details",
        examples=["Registration successful", "Registration failed"]
    )
    successful: bool = Field(
        default=False,
        description="Mark False if no document successfully been processed"
    )
    success_count: int | None = Field(
        default=0,
        description="Number of successfull processed documents",
    )
    failure_count: int | None = Field(
        default=0,
        description="Number of failed processed documents"
    )


class DocumentMetadata(BaseModel):
    id: UUID = Field(
        ..., # generated at db or service layer (service for now)
        description="Unique identifier for processed document"
    )
    document_name: str = Field(
        ...,
        description="Batch documents name",
        examples=["National ID"]
    ) # 1 name per batch
    fields: Annotated[list[DocumentFields], Field(
        min_length=1, 
        max_length=30,
        description="Extracted fields from document under ID"
    )]
    
    
class DocumentRegistrationResponse(BaseModel):
    document_metadata: DocumentMetadata
    details: ResponseDetails


# ========================
# AUTOMATIC FEATURE MODELS
# ========================
class AgentExtractedDocumentMetadata(DocumentRegistrationResponse):
    file_name: str | None = Field(
        ...,
        description="Complete document file name.",
        examples=["national-id.pdf", "mypsa.jpg"]
    )
    confidence_score: float | None = Field(
        0.10,
        description="Agent provided confidence score from 1-100",
        examples=[0.84, 0.92, 0.99]
    )
    needs_review: bool = Field(
        default=False,
        description="Flags if need manual user review and edit."
    )
