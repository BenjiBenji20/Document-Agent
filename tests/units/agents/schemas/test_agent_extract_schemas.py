import pytest
from pydantic import ValidationError
from src.agents.schemas.agent_extract_schemas import (
    BoundingBox, DocumentFields, AgentExtractedDocumentMetadata, AgentExtractedSchemaResponse, ExtractionStatus
)

def test_bounding_box_happy_path():
    box = BoundingBox(ymin=10, xmin=20, ymax=100, xmax=200)
    assert box.ymin == 10
    assert box.xmin == 20
    assert box.ymax == 100
    assert box.xmax == 200

def test_document_fields_happy_path():
    box = BoundingBox(ymin=0, xmin=0, ymax=1000, xmax=1000)
    field = DocumentFields(field="first_name", is_required=True, bounding_box=box)
    assert field.field == "first_name"
    assert field.is_required is True
    assert field.bounding_box.ymax == 1000

def test_agent_extracted_document_metadata_happy_path():
    box = BoundingBox(ymin=10, xmin=10, ymax=90, xmax=90)
    fields = [
        DocumentFields(field="first_name", is_required=True, bounding_box=box),
        DocumentFields(field="last_name", is_required=False, bounding_box=box)
    ]
    meta = AgentExtractedDocumentMetadata(
        document_name="National ID",
        fields=fields,
        file_name="id.jpg",
        confidence_score=0.97
    )
    assert meta.document_name == "National ID"
    assert len(meta.fields) == 2
    assert meta.file_name == "id.jpg"
    assert meta.confidence_score == 0.97

def test_agent_extracted_schema_response_happy_path():
    box = BoundingBox(ymin=0, xmin=0, ymax=10, xmax=10)
    meta = AgentExtractedSchemaResponse(
        id="file-uuid-1234",
        document_name="Driver License",
        fields=[DocumentFields(field="license_no", is_required=True, bounding_box=box)],
        file_name="license.pdf",
        confidence_score=0.88,
        status=ExtractionStatus.SUCCESS,
        error=None
    )
    assert meta.id == "file-uuid-1234"
    assert meta.status == ExtractionStatus.SUCCESS
    assert meta.error is None
