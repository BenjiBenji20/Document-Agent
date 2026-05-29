import pytest
from src.modules.gcs_operations.direct_gcs_operations_schema import *
from pydantic import ValidationError
from uuid import uuid4

# =====================================
# HAPPY TEST PATH GCSUploadFileMetadata model
# =====================================
@pytest.mark.parametrize("valid_data", [
    {
        "file_name": "my National ID",
        "file_type": "application/pdf",
        "file_size": 200
    },{
        "file_name": "i"*255,
        "file_type": "image/jpg",
        "file_size": 1
    },{
        "file_name": "i",
        "file_type": "image/png",
        "file_size": MAX_FILE_SIZE
    }
])
def test_happy_upload_file_metadata(valid_data: list):
    model = GCSUploadFileMetadata(**valid_data)
    assert model.file_name == valid_data["file_name"]
    assert model.file_type == valid_data["file_type"]
    assert model.file_size == valid_data["file_size"]


@pytest.mark.parametrize("invalid_data, error_snippet", [
    # Multiple failures: invalid type, negative size
    ({
        "file_name": "test.png",
        "file_type": "image/webp", # Not allowed
        "file_size": -1            # Must be > 0
    }, "Unsupported file type"),

    # Boundary: Name too long
    ({
        "file_name": "i" * 256,    # Limit is 255
        "file_type": "image/jpg",
        "file_size": 1024
    }, "String should have at most 255 characters"),

    # Boundary: File size is 0 (gt=0 check)
    ({
        "file_name": "empty.pdf",
        "file_type": "application/pdf",
        "file_size": 0
    }, "Input should be greater than 0"),

    # Boundary: Exactly 1 byte over the 10MB limit
    ({
        "file_name": "large.pdf",
        "file_type": "application/pdf",
        "file_size": MAX_FILE_SIZE + 1
    }, "exceeds maximum allowed size"),

    # --- EXTRA ROBUSTNESS CASES ---

    # Wrong Data Types (Pydantic internal check)
    ({
        "file_name": ["not", "a", "string"],
        "file_type": "image/png",
        "file_size": 500
    }, "Input should be a valid string"),

    # Null values for required fields
    ({
        "file_name": "missing_type.png",
        "file_type": None,
        "file_size": 500
    }, "Input should be a valid string"),

    # Sneaky injection-style MIME type
    ({
        "file_name": "hack.png",
        "file_type": "image/png; charset=utf-8", # Regex/Exact match check
        "file_size": 500
    }, "Unsupported file type")
])
def test_negative_upload_file_metadata(invalid_data, error_snippet):
    with pytest.raises(ValidationError) as excinfo:
        GCSUploadFileMetadata(**invalid_data)
    
    # Verify the error message contains the snippet we expect
    assert error_snippet in str(excinfo.value)

# =====================================
# HAPPY TEST PATH GCSUploadURLResponse model
# =====================================
@pytest.mark.parametrize("valid_data", [
    {
        "id": str(uuid4()),
        "storage_path": "api/public/ip/date/id/my_ID",
        "upload_url": "https://api/public/ip/date/id/my_ID",
        "expires_in_seconds": 3600
    },
    {
        "id": str(uuid4()),
        "storage_path": "i",
        "upload_url": "i",
        "expires_in_seconds": 10
    },
    {
        "id": str(uuid4()),
        "storage_path": "i"*510,
        "upload_url": "_",
        "expires_in_seconds": 3599
    }
])

def test_happy_gcs_upload_url_response(valid_data: list):
    model = GCSUploadURLResponse(**valid_data)
    assert model.id == valid_data["id"]
    assert model.storage_path == valid_data["storage_path"]
    assert model.upload_url == valid_data["upload_url"]
    assert model.expires_in_seconds == valid_data["expires_in_seconds"]
    

@pytest.mark.parametrize("invalid_data, error_snippet", [
    # Missing all required fields (the "Empty Body" test)
    ({}, "Field required"),

    # upload_url: Empty string (min_length=1 violation)
    ({
        "id": str(uuid4()),
        "upload_url": "", 
        "storage_path": "/api/public/"
    }, "String should have at least 1 character"),

    # storage_path: Empty string (min_length=1 violation)
    ({
        "id": str(uuid4()),
        "upload_url": "https://gcs.com/upload",
        "storage_path": ""
    }, "String should have at least 1 character"),

    # storage_path: Too long (Boundary: 511 characters)
    ({
        "id": str(uuid4()),
        "upload_url": "https://gcs.com/upload",
        "storage_path": "a" * 511
    }, "String should have at most 510 characters"),

    # expires_in_seconds: Wrong type (Passing a string instead of int)
    ({
        "id": str(uuid4()),
        "upload_url": "https://gcs.com/upload",
        "storage_path": "/api/public/",
        "expires_in_seconds": "ten seconds"
    }, "Input should be a valid integer"),

    # Providing 'null' for a required field (id) 
    # Note: Because of `...`, Pydantic expects the key to exist even if value is None
    ({
        "id": None,
        "upload_url": "https://gcs.com/upload",
        "storage_path": "/api/public/"
    }, None) # This should actually PASS if typed as str | None. 
             # To make it fail, remove '| None' from the model type.
])
def test_negative_gcs_upload_url_response(invalid_data, error_snippet):
    # If error_snippet is None, we expect this case to PASS (testing the optionality)
    if error_snippet is None:
        GCSUploadURLResponse(**invalid_data)
    else:
        with pytest.raises(ValidationError) as excinfo:
            GCSUploadURLResponse(**invalid_data)
        assert error_snippet in str(excinfo.value)    
