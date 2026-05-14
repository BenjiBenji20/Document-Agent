from pydantic import BaseModel, Field
from shared.file_metadata import ALLOWED_MIME_TYPES, MAX_FILE_SIZE

class GenerateGCSUploadURL(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=255)
    file_type: str = Field(
        ..., 
        description="MIME type of the file",
        examples=[".jpg", ".png", ".pdf", ".jpeg"]
    )
    file_size: int = Field(..., gt=0, description="File size in bytes")
    
    
    def validate_file_type(self) -> None:
        if self.file_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported file type: {self.file_type}")

    def validate_file_size(self) -> None:
        if self.file_size > MAX_FILE_SIZE:
            raise ValueError(
                f"File size {self.file_size} exceeds maximum allowed size of {MAX_FILE_SIZE} bytes."
            )
