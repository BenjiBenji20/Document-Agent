from unittest.mock import AsyncMock
from uuid import uuid4

from pydantic import ValidationError
import pytest
from src.modules.fields_registration.document_registration_schema import *

# ============================================================
# HAPPY PATH TESTS - pydantic model
# ============================================================

# =====================================
# TEST document fields
# =====================================
@pytest.mark.parametrize("valid_data", [
    {
        "field": "complete_address",
        "is_required": True
    }, {
        "field": "i", # min length test
        "is_required": True
    }, {
        "field": "i"*30, # max length test
        "is_required": True
    }
])
def test_happy_document_fields_validation(valid_data: list):
    model = DocumentFields(**valid_data)
    assert model.field == valid_data["field"]
    assert model.is_required == valid_data["is_required"]
        
def test_document_fields_defaults():
    default = DocumentFields(field="first_name")
    assert default.field == "first_name"
    assert default.is_required is False
    

# =====================================
# TEST DocumentRegistrationRequest
# =====================================
@pytest.mark.parametrize("input_data", [
    # Case 1: Standard valid data
    {
        "document_name": "Barangay Clearance",
        "fields": [{"field": "pangalan"}, {"field": "apelyido"}, {"field": "edad"}],
        "honeypot": None
    },
    # Case 2: Test minimum lengths (1 char name, 1 field)
    {
        "document_name": "i",
        "fields": [{"field": "i"}],
        "honeypot": ""  # Honeypot accepts None or empty string
    },
    # Case 3: Test maximum boundaries (100 char name, 30 fields)
    {
        "document_name": "i" * 100,
        "fields": [{"field": f"field-{n}"} for n in range(30)],
        "honeypot": None
    }
])
def test_happy_document_registration_request_validation(input_data):
    # Act
    model = DocumentRegistrationRequest(**input_data)
    
    # Assert - Document Name
    assert model.document_name == input_data["document_name"]
    
    # Assert - Fields (Check length and specific values)
    assert len(model.fields) == len(input_data["fields"])
    for i, field_obj in enumerate(model.fields):
        # We check .field because DocumentFields is a model, not a string
        assert field_obj.field == input_data["fields"][i]["field"].lower().strip()
    
    # Assert - Honeypot
    assert model.honeypot == input_data["honeypot"]

def test_document_registration_request_fields_uniqueness():
    # Arrange: Create request with duplicate fields (exact match and different flags)
    input_data = {
        "document_name": "Unique Check",
        "fields": [
            {"field": "first_name", "is_required": True},
            {"field": "last_name", "is_required": True},
            {"field": "first_name", "is_required": False}, # Duplicate name!
            {"field": "age", "is_required": False},
            {"field": "last_name", "is_required": False}   # Duplicate name!
        ]
    }
    
    # Act
    model = DocumentRegistrationRequest(**input_data)
    
    # Assert
    assert len(model.fields) == 3
    assert model.fields[0].field == "first_name"
    assert model.fields[0].is_required is True # Took the first one
    assert model.fields[1].field == "last_name"
    assert model.fields[2].field == "age"


# =====================================
# TEST ResponseDetails
# =====================================
def test_response_details_happy_path():
    # Min/Empty case
    res = ResponseDetails()
    assert res.successful is False
    assert res.success_count == 0

    # Full case
    res_full = ResponseDetails(description="Done", successful=True, success_count=5, failure_count=2)
    assert res_full.success_count == 5
    

# =====================================
# TEST DocumentMetadata & RegistrationResponse
# =====================================
@pytest.mark.parametrize("field_count", [1, 30]) # Boundary: Min 1, Max 30
def test_document_registration_response_happy_path(field_count):
    input_data = {
        "document_metadata": {
            "id": uuid4(),
            "document_name": "Testing Boundaries",
            "fields": [{"field": f"f_{i}"} for i in range(field_count)]
        },
        "details": {"successful": True}
    }
    model = DocumentRegistrationResponse(**input_data)
    assert len(model.document_metadata.fields) == field_count


# ============================================================
# NEGATIVE PATH TESTS - pydantic model
# ============================================================

# =====================================
# TEST document fields
# =====================================
def test_negative_document_fields_validation():
    # max length = 30, 31 should fail
    with pytest.raises(ValidationError) as excinfo:
        DocumentFields(field="i"*31)
    assert "String should have at most 30 characters" in str(excinfo.value)
    
    # min length = 1, 0 should fail
    with pytest.raises(ValidationError) as excinfo:
        DocumentFields(field="")
    assert "String should have at least 1 character" in str(excinfo.value)
    
    # passing whitespace and strip it so field is 0 char
    with pytest.raises(ValidationError) as excinfo:
        DocumentFields(field=" ")
    assert "at least 1 character" in str(excinfo.value) or "blank" in str(excinfo.value)
    
    # invalid values
    with pytest.raises(ValidationError) as excinfo:
        DocumentFields(field="valid_name", is_required="not-a-boolean")
    assert "Input should be a valid boolean" in str(excinfo.value)


# =====================================
# TEST DocumentRegistrationRequest
# =====================================
def test_negative_document_registration_request_validation():
    # 1. document_name: Injection attempt (SafeLabel check)
    with pytest.raises(ValidationError) as excinfo:
        DocumentRegistrationRequest(
            document_name="<script>alert(1)</script>",
            fields=[{"field": "test"}]
        )
    assert "Invalid characters detected" in str(excinfo.value)

    # 2. document_name: Too long (> 100)
    with pytest.raises(ValidationError) as excinfo:
        DocumentRegistrationRequest(
            document_name="a" * 101,
            fields=[{"field": "test"}]
        )
    assert "at most 100 characters" in str(excinfo.value)

    # 3. fields: Empty list (min_length=1)
    with pytest.raises(ValidationError) as excinfo:
        DocumentRegistrationRequest(
            document_name="Valid Name",
            fields=[]  # Violates min_length=1
        )
    assert "at least 1 item" in str(excinfo.value) or "too_short" in str(excinfo.value)

    # 4. fields: Too many items (> 30)
    with pytest.raises(ValidationError) as excinfo:
        DocumentRegistrationRequest(
            document_name="Valid Name",
            fields=[{"field": f"f{i}"} for i in range(31)]
        )
    assert "at most 30 items" in str(excinfo.value)

    # 5. honeypot: Triggered
    with pytest.raises(ValidationError) as excinfo:
        DocumentRegistrationRequest(
            document_name="Valid Name",
            fields=[{"field": "test"}],
            honeypot="I am a bot"
        )
    assert "Automatic request denied" in str(excinfo.value)
    

# =====================================
# TEST DocumentMetadata & RegistrationResponse
# =====================================
def test_document_registration_negative_paths():
    # 1. Test min_length = 1 (Zero items should fail)
    with pytest.raises(ValidationError) as exc:
        DocumentMetadata(
            id=uuid4(),
            document_name="Empty",
            fields=[] # Error: Too short
        )
    assert "at least 1 item" in str(exc.value)

    # 2. Test max_length = 30 (31 items should fail)
    with pytest.raises(ValidationError) as exc:
        DocumentMetadata(
            id=uuid4(),
            document_name="Too Many",
            fields=[{"field": "f"}] * 31 # Error: Too long
        )
    assert "at most 30 items" in str(exc.value)
        