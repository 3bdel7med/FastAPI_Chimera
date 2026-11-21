"""Responsibility: read `relationship(...)` declarations and decide what kind of relation each one is."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from fast_chimera.shift.extraction.annotations import Annotation
from fast_chimera.shift.extraction.ast_utils import bool_value, keyword_map, last_name_of, shorten, string_value
from fast_chimera.shift.schema import RelationInfo, TableInfo
from fast_chimera.shift.schema.tables import RelationType

RELATION_FUNCTIONS = frozenset({"relationship", "Relationship"})


@dataclass
class PendingRelation:
    """What the class body says; the final type is decided later, when every table is known."""

    name: str
    target: str | None
    is_collection: bool | None  # from the annotation; None when there is no annotation
    uselist: bool | None
    secondary_table: str | None
    back_populates: str | None


def parse_relation(
    name: str,
    call: ast.Call,
    annotation: Annotation | None,
    association_tables: dict[str, str],
) -> PendingRelation:
    keywords = keyword_map(call)

    target = last_name_of(call.args[0]) if call.args else None
    if target is None and annotation is not None and annotation.core is not None:
        target = last_name_of(annotation.core)

    secondary_expression = keywords.get("secondary")
    secondary_table = None
    if secondary_expression is not None:
        variable = last_name_of(secondary_expression) or ""
        secondary_table = (
            string_value(secondary_expression) or association_tables.get(variable) or shorten(ast.unparse(secondary_expression))
        )

    return PendingRelation(
        name=name,
        target=target,
        is_collection=annotation.is_collection if annotation else None,
        uselist=bool_value(keywords.get("uselist")),
        secondary_table=secondary_table,
        back_populates=string_value(keywords.get("back_populates")) or string_value(keywords.get("backref")),
    )


def resolve_relation(table: TableInfo, pending: PendingRelation, tables_by_model: dict[str, TableInfo]) -> RelationInfo:
    target_table = tables_by_model.get(pending.target or "")
    target_table_name = target_table.name if target_table else None

    return RelationInfo(
        name=pending.name,
        type=_decide_type(table, pending, target_table_name),
        target=pending.target or "?",
        target_table=target_table_name,
        back_populates=pending.back_populates,
        through=pending.secondary_table,
    )


def _decide_type(table: TableInfo, pending: PendingRelation, target_table_name: str | None) -> RelationType:
    if pending.target is None:
        return "unknown"
    if pending.secondary_table:
        return "many_to_many"
    if pending.uselist is True or pending.is_collection:
        return "has_many"
    if _has_foreign_key_to(table, target_table_name):
        return "belongs_to"  # this table holds the foreign key
    if pending.is_collection is False or pending.uselist is False:
        return "has_one"
    return "has_many"  # no annotation and no hint: SQLAlchemy's default is a collection


def _has_foreign_key_to(table: TableInfo, target_table_name: str | None) -> bool:
    if target_table_name is None:
        return False
    for column in table.columns:
        if column.foreign_key and column.foreign_key.split(".")[0] == target_table_name:
            return True
    return False
