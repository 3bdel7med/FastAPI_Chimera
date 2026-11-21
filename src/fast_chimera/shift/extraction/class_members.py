"""Responsibility: collect the columns, relations and constraints a model class declares,
including the ones it inherits from mixins."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from fast_chimera.shift.extraction.annotations import unwrap_annotation
from fast_chimera.shift.extraction.ast_utils import assignment_parts, last_name_of
from fast_chimera.shift.extraction.class_index import ClassIndex
from fast_chimera.shift.extraction.columns import COLUMN_FUNCTIONS, ColumnParser
from fast_chimera.shift.extraction.relations import RELATION_FUNCTIONS, PendingRelation, parse_relation
from fast_chimera.shift.extraction.source_modules import SourceModule
from fast_chimera.shift.extraction.table_args import parse_table_args
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes
from fast_chimera.shift.schema import ColumnInfo, IndexInfo


@dataclass
class ClassMembers:
    columns: dict[str, ColumnInfo] = field(default_factory=dict)
    relations: dict[str, PendingRelation] = field(default_factory=dict)
    unique_constraints: list[list[str]] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)

    def absorb(self, inherited: ClassMembers) -> None:
        self.columns.update(inherited.columns)
        self.relations.update(inherited.relations)
        self.unique_constraints += inherited.unique_constraints
        self.indexes += inherited.indexes


class ClassMemberCollector:
    def __init__(
        self,
        class_index: ClassIndex,
        column_parser: ColumnParser,
        association_tables: dict[str, str],
        notes: UnresolvedNotes,
    ) -> None:
        self._classes = class_index
        self._columns = column_parser
        self._association_tables = association_tables
        self._notes = notes

    def collect(
        self,
        module: SourceModule,
        class_def: ast.ClassDef,
        is_sqlmodel_table: bool,
        visiting: frozenset[int] = frozenset(),
    ) -> ClassMembers:
        members = ClassMembers()

        # Inherited members first, so a subclass can override them.
        for base_expression in class_def.bases:
            found = self._classes.find_base_class(module, base_expression)
            if found is not None and id(found[1]) not in visiting:
                base_module, base_class = found
                members.absorb(self.collect(base_module, base_class, is_sqlmodel_table, visiting | {id(class_def)}))

        for statement in class_def.body:
            self._read_statement(module, statement, is_sqlmodel_table, members)
        return members

    def _read_statement(self, module: SourceModule, statement: ast.stmt, is_sqlmodel_table: bool, members: ClassMembers) -> None:
        name, value, annotation_node = assignment_parts(statement)
        if not name:
            return

        if name == "__table_args__":
            parse_table_args(module, value, members.unique_constraints, members.indexes, self._notes)
            return
        if name.startswith("__"):
            return

        annotation = unwrap_annotation(annotation_node) if annotation_node is not None else None
        function_name = last_name_of(value.func) if isinstance(value, ast.Call) else None

        if function_name in RELATION_FUNCTIONS and isinstance(value, ast.Call):
            members.columns.pop(name, None)
            members.relations[name] = parse_relation(name, value, annotation, self._association_tables)
        elif function_name in COLUMN_FUNCTIONS and isinstance(value, ast.Call):
            members.columns[name] = self._columns.parse(module, name, value, annotation)
        elif value is None and annotation is not None and annotation.wrapped_in_mapped:
            members.columns[name] = self._columns.parse(module, name, None, annotation)  # `x: Mapped[int]`
        elif is_sqlmodel_table and annotation is not None and last_name_of(annotation_node) != "ClassVar":
            members.columns[name] = self._columns.parse(module, name, None, annotation)  # plain SQLModel field
