"""Responsibility: peel the wrappers off a type annotation.

`Mapped[Optional[list["Product"]]]` -> core `Product`, optional, collection, wrapped in Mapped."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from fast_chimera.shift.extraction.ast_utils import is_none_constant, last_name_of

COLLECTION_NAMES = frozenset({"list", "List", "Sequence", "set", "Set", "Iterable", "tuple", "Tuple"})
MAX_WRAPPER_LAYERS = 12


@dataclass
class Annotation:
    core: ast.expr | None = None
    optional: bool = False
    is_collection: bool = False
    wrapped_in_mapped: bool = False


def unwrap_annotation(annotation: ast.expr | None) -> Annotation:
    result = Annotation()
    node = annotation
    for _ in range(MAX_WRAPPER_LAYERS):
        if node is None:
            break
        inner = _peel_one_layer(node, result)
        if inner is None:
            break
        node = inner
    result.core = node
    return result


def annotated_metadata_calls(annotation: ast.expr | None) -> list[ast.expr]:
    """For `Annotated[int, Depends(x)]` return [Depends(x)]."""
    if isinstance(annotation, ast.Subscript) and last_name_of(annotation.value) == "Annotated":
        return _subscript_arguments(annotation)[1:]
    return []


def strip_annotated(annotation: ast.expr) -> ast.expr:
    """For `Annotated[int, Depends(x)]` return `int`."""
    if isinstance(annotation, ast.Subscript) and last_name_of(annotation.value) == "Annotated":
        return _subscript_arguments(annotation)[0]
    return annotation


def _subscript_arguments(node: ast.Subscript) -> list[ast.expr]:
    inside = node.slice
    return list(inside.elts) if isinstance(inside, ast.Tuple) else [inside]


def _peel_one_layer(node: ast.expr, result: Annotation) -> ast.expr | None:
    """Remove one wrapper, record what it meant in `result`, and return the inner node.
    Returns None when there is nothing left to peel."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _parse_forward_reference(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _peel_union_with_none(node, result)
    if isinstance(node, ast.Subscript):
        return _peel_subscript(node, result)
    return None


def _parse_forward_reference(text: str) -> ast.expr | None:
    try:
        return ast.parse(text.strip(), mode="eval").body
    except SyntaxError:
        return None


def _peel_union_with_none(node: ast.BinOp, result: Annotation) -> ast.expr | None:
    """`X | None` or `None | X`."""
    if is_none_constant(node.right):
        result.optional = True
        return node.left
    if is_none_constant(node.left):
        result.optional = True
        return node.right
    return None


def _peel_subscript(node: ast.Subscript, result: Annotation) -> ast.expr | None:
    name = last_name_of(node.value)
    arguments = _subscript_arguments(node)

    if name == "Mapped":
        result.wrapped_in_mapped = True
        return arguments[0]
    if name == "Annotated":
        return arguments[0]
    if name == "Optional":
        result.optional = True
        return arguments[0]
    if name == "Union":
        not_none = [argument for argument in arguments if not is_none_constant(argument)]
        if len(not_none) < len(arguments):
            result.optional = True
        return not_none[0] if not_none else None
    if name in COLLECTION_NAMES:
        result.is_collection = True
        return arguments[0]
    return None
