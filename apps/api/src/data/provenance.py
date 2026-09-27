"""Provenance constructors so labels are consistent across API, UI and reports (CLAUDE.md §5, §32)."""
from ..schemas.provenance import Provenance


def observed(source_name: str, source_url: str | None = None, notes: str | None = None) -> Provenance:
    return Provenance(type="observed", source_name=source_name, source_url=source_url, notes=notes)


def derived(source_name: str, notes: str) -> Provenance:
    return Provenance(type="derived", source_name=source_name, notes=notes)


def modeled(source_name: str, notes: str) -> Provenance:
    return Provenance(type="modeled", source_name=source_name, notes=notes)


def hypothetical(notes: str) -> Provenance:
    return Provenance(type="hypothetical", notes=notes)
