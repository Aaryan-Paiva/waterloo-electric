from typing import Literal, Optional

from .base import CamelModel

ProvenanceType = Literal["observed", "modeled", "hypothetical", "derived"]


class Provenance(CamelModel):
    """CLAUDE.md §32. Every important number carries one. Never silently convert modeled -> observed."""
    type: ProvenanceType
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    notes: Optional[str] = None
