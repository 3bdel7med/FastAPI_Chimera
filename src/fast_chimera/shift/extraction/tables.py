"""Responsibility: find every table: ORM model classes and plain association (pivot) tables."""

from __future__ import annotations

import ast

from fast_chimera.shift.extraction.ast_utils import assignment_parts, bool_value, last_name_of, string_value
from fast_chimera.shift.extraction.class_index import ClassIndex
from fast_chimera.shift.extraction.class_members import ClassMemberCollector, ClassMembers
from fast_chimera.shift.extraction.columns import ColumnParser
from fast_chimera.shift.extraction.relations import PendingRelation, resolve_relation
from fast_chimera.shift.extraction.source_modules import SourceModule
from fast_chimera.shift.extraction.unresolved import UnresolvedNotes
from fast_chimera.shift.schema import TableInfo


class TableExtractor:
    def __init__(self, modules: list[SourceModule], class_index: ClassIndex, notes: UnresolvedNotes) -> None:
        self._modules = modules
        self._classes = class_index
        self._notes = notes
        self._columns = ColumnParser(notes)

    def extract(self) -> list[TableInfo]:
        # Association tables first: a relationship may name one that is declared further down the file.
        association_tables, association_variables = self._find_association_tables()
        collector = ClassMemberCollector(self._classes, self._columns, association_variables, self._notes)

        model_tables: list[TableInfo] = []
        pending_relations: list[tuple[TableInfo, list[PendingRelation]]] = []
        for module in self._modules:
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                table_name = self._table_name_of(module, node)
                if table_name is None:
                    continue
                members = collector.collect(module, node, _is_sqlmodel_table(node))
                table = self._build_table(module, node, table_name, members)
                model_tables.append(table)
                pending_relations.append((table, list(members.relations.values())))

        tables_by_model = {table.model: table for table in model_tables if table.model}
        for table, pending in pending_relations:
            table.relations = [resolve_relation(table, relation, tables_by_model) for relation in pending]
        return model_tables + association_tables

    @staticmethod
    def _build_table(module: SourceModule, class_def: ast.ClassDef, name: str, members: ClassMembers) -> TableInfo:
        return TableInfo(
            name=name,
            model=class_def.name,
            module=module.name,
            columns=list(members.columns.values()),
            unique_constraints=members.unique_constraints,
            indexes=members.indexes,
        )

    def _table_name_of(self, module: SourceModule, class_def: ast.ClassDef) -> str | None:
        for statement in class_def.body:
            name, value, _ = assignment_parts(statement)
            if name == "__abstract__" and bool_value(value):
                return None
            if name == "__tablename__":
                constant = string_value(value)
                if constant is None:
                    self._notes.add(module.path, statement, f"{class_def.name}: __tablename__ is not a constant")
                return constant
        if _is_sqlmodel_table(class_def):
            return class_def.name.lower()  # SQLModel's default table name
        return None

    def _find_association_tables(self) -> tuple[list[TableInfo], dict[str, str]]:
        """`product_tags = Table("product_tags", Base.metadata, Column(...), ...)`"""
        tables: list[TableInfo] = []
        variable_to_table: dict[str, str] = {}
        for module in self._modules:
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                    continue
                call = node.value
                if last_name_of(call.func) != "Table" or not call.args:
                    continue
                table_name = string_value(call.args[0])
                if table_name is None:
                    continue

                columns = [
                    self._columns.parse(module, string_value(arg.args[0]) or "", arg, None)
                    for arg in call.args[1:]
                    if isinstance(arg, ast.Call) and last_name_of(arg.func) == "Column" and arg.args and string_value(arg.args[0])
                ]
                tables.append(TableInfo(name=table_name, kind="association", module=module.name, columns=columns))
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    variable_to_table[node.targets[0].id] = table_name
        return tables, variable_to_table


def _is_sqlmodel_table(class_def: ast.ClassDef) -> bool:
    keywords = {keyword.arg: keyword.value for keyword in class_def.keywords if keyword.arg}
    return bool(bool_value(keywords.get("table")))
