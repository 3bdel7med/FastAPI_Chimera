"""The fingerprint itself: names, types and shapes only. Never source code, defaults or secret values."""

from __future__ import annotations

from pydantic import BaseModel, Field

from fast_chimera.shift.schema.endpoints import EndpointInfo, MiddlewareInfo
from fast_chimera.shift.schema.tables import TableInfo

SCHEMA_VERSION = 1


class Fingerprint(BaseModel):
    schema_version: int = SCHEMA_VERSION
    generator: str
    framework: str = "fastapi"
    project: str
    generated_at: str
    content_sha256: str = ""
    tables: list[TableInfo] = Field(default_factory=list)
    endpoints: list[EndpointInfo] = Field(default_factory=list)
    middleware: list[MiddlewareInfo] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list, description="Things static analysis could not determine")

    def to_json(self, *, indent: int | None = 2) -> str:
        return self.model_dump_json(exclude_none=True, indent=indent)

    def stats(self) -> dict[str, int]:
        return {
            "tables": len(self.tables),
            "columns": sum(len(table.columns) for table in self.tables),
            "relations": sum(len(table.relations) for table in self.tables),
            "endpoints": len(self.endpoints),
            "middleware": len(self.middleware),
            "unresolved": len(self.unresolved),
        }
