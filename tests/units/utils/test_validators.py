import pytest
from pydantic import BaseModel, ValidationError
from src.utils.validators import SafeLabel, FieldName, Honeypot

# Setup a dummy model for testing the types
class SchemaTester(BaseModel):
    label: SafeLabel
    field: FieldName
    bot_check: Honeypot = None

# ============================================================
# HAPPY PATH TESTS - 1 per validator and annotated
# ============================================================

@pytest.mark.parametrize("valid_label", [
    "Document Title",
    "User-Profile_99",
    "It's a beautiful day",  # Apostrophe check
    "  Whitespace Stripped  ",
])
def test_safe_label_happy_path(valid_label: str):
    instance = SchemaTester(label=valid_label, field="valid-field")
    assert instance.label == valid_label.strip()

@pytest.mark.parametrize("valid_field", [
    "first_name",
    "date-of-birth",
    "address1",
    "  lowercase-me  ",
    "UpperCase_Field",
])
def test_field_name_happy_path(valid_field: str):
    instance = SchemaTester(label="Valid", field=valid_field)
    assert instance.field == valid_field.strip().lower()

def test_honeypot_happy_path():
    # None and empty string should pass
    assert SchemaTester(label="V", field="f", bot_check=None).bot_check is None
    assert SchemaTester(label="V", field="f", bot_check="").bot_check == ""


# ============================================================
# NEGATIVE PATH TESTS - 1 per validator and annotated
# ============================================================

@pytest.mark.parametrize("invalid_label, error_snippet", [
    ("<script>", "Invalid characters detected"),
    ("Drop table;", "Invalid characters detected"),
    ("{admin_flag}", "Invalid characters detected"),
    ("   ", "Value must not be blank"),
    ("A" * 101, "Invalid characters detected"), # Length check
])
def test_safe_label_failure(invalid_label, error_snippet):
    with pytest.raises(ValidationError) as excinfo:
        SchemaTester(label=invalid_label, field="valid")
    assert error_snippet in str(excinfo.value)

@pytest.mark.parametrize("invalid_field, error_snippet", [
    # Starts with a number (Regex block)
    ("123-start-with-number", "Must be lowercase, start with a letter"),
    # Contains invalid special characters (Regex block)
    ("special@char", "Invalid field name"),
    ("field.name", "Invalid field name"),
    ("field name", "Invalid field name"),
    # Empty after stripping (Blank check)
    ("   ", "Field name must not be blank"),
    ("", "Field name must not be blank"),
    # Exceeds 50 characters (Regex block)
    ("a" * 51, "Invalid field name"),
])
def test_field_name_failure(invalid_field, error_snippet):
    with pytest.raises(ValidationError) as excinfo:
        SchemaTester(label="Valid", field=invalid_field)
    assert error_snippet in str(excinfo.value)

def test_honeypot_failure():
    with pytest.raises(ValidationError) as excinfo:
        SchemaTester(label="Valid", field="valid", bot_check="I am a bot")
    assert "Automatic request denied" in str(excinfo.value)
    