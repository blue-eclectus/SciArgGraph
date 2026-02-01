"""Pydantic models matching the argument graph ontology."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TextualBasisSpan(BaseModel):
    """A single verbatim quote from source text."""

    text: str = Field(..., description="Verbatim quote from source text")
    location: str | None = Field(
        None, description="Where in the source document"
    )


# TextualBasis can be single span or array of spans
TextualBasis = TextualBasisSpan | list[TextualBasisSpan]


class Proposition(BaseModel):
    """A truth-valued claim without explicit provenance."""

    type: Literal["Proposition"] = "Proposition"
    id: str
    content: str
    base_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    textual_basis: TextualBasis | None = None
    duplicate_of: str | None = Field(default=None, description="ID of canonical node if this is a duplicate")
    explicitness: Literal["explicit", "implicit", "inferred"] | None = Field(
        default=None,
        description="How directly the proposition was stated: 'explicit' if stated, 'implicit' if inferrable, 'inferred' if reconstructed"
    )
    auxiliary: bool = Field(
        default=False,
        description="True if this proposition serves as a supporting premise in a joint link (visualized with dashed edges)"
    )


class Conclusion(BaseModel):
    """The final claim of an argument thread."""

    type: Literal["Conclusion"] = "Conclusion"
    id: str
    content: str
    base_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    argument_id: str | None = None
    textual_basis: TextualBasis | None = None
    duplicate_of: str | None = Field(default=None, description="ID of canonical node if this is a duplicate")


class Datum(BaseModel):
    """A reported finding with associated source."""

    type: Literal["Datum"] = "Datum"
    id: str
    content: str
    source: str  # Required for Datums
    base_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    textual_basis: TextualBasis | None = None
    duplicate_of: str | None = Field(default=None, description="ID of canonical node if this is a duplicate")


class Link(BaseModel):
    """Reified support or undermine relationship."""

    type: Literal["Link"] = "Link"
    id: str
    source_ids: list[str] = Field(..., min_length=1)
    target_id: str
    polarity: Literal["supports", "undermines"]
    strength: float = Field(default=0.8, ge=0.0, le=1.0)
    explicitness: Literal["explicit", "implicit", "inferred"] | None = None
    textual_basis: TextualBasis | None = None


# Type alias for discriminated union of node types
Node = Proposition | Conclusion | Datum | Link
