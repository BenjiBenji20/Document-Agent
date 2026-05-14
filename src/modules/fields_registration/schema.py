from typing import Annotated
from uuid import UUID

import magic  # python-magic
from fastapi import UploadFile
from pydantic import BaseModel, field_validator, ConfigDict, Field
from shared.file_metadata import ALLOWED_MIME_TYPES, MAX_FILE_SIZE
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
    
class FileUpload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file: UploadFile

    @field_validator("file")
    @classmethod
    async def validate_file(cls, file: UploadFile) -> UploadFile:
        # Read a small header chunk — enough for magic byte detection
        header = await file.read(2048)
        
        # Detect MIME from actual bytes, not the filename or Content-Type header
        detected_mime = magic.from_buffer(header, mime=True)
        if detected_mime not in ALLOWED_MIME_TYPES:
            raise ValueError(
                f"Unsupported file type '{detected_mime}'. "
                f"Allowed: pdf, png, jpg, jpeg."
            )

        # Check file size without loading the whole file into memory
        await file.seek(0)
        size = 0
        while chunk := await file.read(8192):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                raise ValueError("File exceeds the 10MB size limit.")

        # Reset cursor so the endpoint can read the file normally after validation
        await file.seek(0)
        return file
    
    
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
    needs_review: False = Field(
        False,
        description="Flags if need manual user review and edit."
    )
