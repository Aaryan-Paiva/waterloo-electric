from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """API models serialise as camelCase (matches the TypeScript contracts in CLAUDE.md §12)."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
