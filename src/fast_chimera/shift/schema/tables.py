"""Database part of the fingerprint: tables, columns, relations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str = "unknown"
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    index: bool = False
    foreign_key: str | None = None  # "vendors.id"
    on_delete: str | None = None


class IndexInfo(BaseModel):
    name: str | None = None
    columns: list[str]
    unique: bool = False


RelationType = Literal["belongs_to", "has_one", "has_many", "many_to_many", "unknown"]


class RelationInfo(BaseModel):
    name: str
    type: RelationType
    target: str  # model class name
    target_table: str | None = None
    back_populates: str | None = None
    through: str | None = None  # pivot table for many_to_many


class TableInfo(BaseModel):
    name: str
    kind: Literal["model", "association"] = "model"
    model: str | None = None
    module: str
    columns: list[ColumnInfo] = Field(default_factory=list)
    relations: list[RelationInfo] = Field(default_factory=list)
    unique_constraints: list[list[str]] = Field(default_factory=list)
    indexes: list[IndexInfo] = Field(default_factory=list)
