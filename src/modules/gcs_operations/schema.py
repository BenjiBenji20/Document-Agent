from pydantic import BaseModel, Field, field_validator
from src.shared.file_metadata import ALLOWED_MIME_TYPES, MAX_FILE_SIZE

class GenerateGCSUploadURL(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=255)
    file_type: str = Field(
        ..., 
        description="MIME type of the file",
        examples=[".jpg", ".png", ".pdf", ".jpeg"]
    )
    file_size: int = Field(..., gt=0, description="File size in bytes")
    
    @field_validator("file_type")
    @classmethod
    def validate_file_type(cls, file_type: str) -> None:
        if file_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported file type: {file_type}")

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, file_size: int) -> None:
        if file_size > MAX_FILE_SIZE:
            raise ValueError(
                f"File size {file_size} exceeds maximum allowed size of {MAX_FILE_SIZE} bytes."
            )


# ==============================+
# Internal or Output only schemas
# ===============================
class GCSUploadURLResponse(BaseModel):
    id: str | None = Field(
        ..., description="File unique identifier."
    )
    upload_url: str | None = Field(
        ...,
        min_length=1,
        description="GCS layer generated upload URL via stored flat object."
    )
    storage_path: str | None = Field(
        ...,
        min_length=1,
        max_length=510,
        description="Service layer defined and as file dir in GCS",
        examples=["/api/public/", "/api/private/"]
    )
    expires_in_seconds: int | None = Field(
        10,
        description="1hr upload expiration in seconds"
    )
    