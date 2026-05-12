import re
from typing import Annotated
from pydantic import AfterValidator

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Allows: letters (Unicode), digits, spaces, hyphens, underscores, apostrophes.
# Blocks: angle brackets, braces, quotes, semicolons — the core prompt-injection chars.
_SAFE_LABEL_RE = re.compile(r"^[\w\s\-']{1,100}$", re.UNICODE)

# Snake/kebab-case identifiers only: "first_name", "date-of-birth", etc.
# Keeps field names clean and safe to embed directly into prompts as-is.
_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_\-]{0,49}$")


# ---------------------------------------------------------------------------
# Reusable validator functions (use with Annotated + AfterValidator)
# ---------------------------------------------------------------------------

def validate_safe_label(value: str) -> str:
    """
    Validates a human-readable label (document name, display title, etc.).
    Strips leading/trailing whitespace first, then enforces the safe pattern.
    Blocks prompt-injection vectors: <tags>, {braces}, quotes, semicolons.
    """
    value = value.strip()
    if not value:
        raise ValueError("Value must not be blank after stripping whitespace.")
    if not _SAFE_LABEL_RE.match(value):
        raise ValueError(
            f"Invalid characters detected in label: '{value}'. "
            "Only letters, digits, spaces, hyphens, underscores, and apostrophes are allowed."
        )
    return value


def validate_field_name(value: str) -> str:
    """
    Validates a field identifier intended for agent extraction schemas.
    Enforces snake_case / kebab-case, lowercase only, max 50 chars.
    Prevents prompt injection through field names embedded in agent prompts.
    """
    value = value.strip().lower()
    if not value:
        raise ValueError("Field name must not be blank.")
    if not _FIELD_NAME_RE.match(value):
        raise ValueError(
            f"Invalid field name: '{value}'. "
            "Must be lowercase, start with a letter, and contain only letters, digits, underscores, or hyphens (max 50 chars)."
        )
    return value


def validate_honeypot(value: str | None) -> str | None:
    """
    Honeypot must be None or an empty string.
    Any bot that auto-fills this field is immediately rejected.
    """
    if value not in (None, ""):
        raise ValueError("Automatic request denied.")  # Intentionally vague
    return value


# ---------------------------------------------------------------------------
# Annotated types
# ---------------------------------------------------------------------------

SafeLabel = Annotated[str, AfterValidator(validate_safe_label)]
FieldName = Annotated[str, AfterValidator(validate_field_name)]
Honeypot  = Annotated[str | None, AfterValidator(validate_honeypot)]