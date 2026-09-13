"""
Deterministic post-processing over data already fetched from OpenStack
(filter / count / group-by / sort / top-n). This exists so the model never has
to "eyeball-count" a large JSON list in its own context - it emits a small
structured operation spec, this runs it with real code, and the exact result
is handed back for the model to phrase in natural language.

No eval()/exec() anywhere - operations and comparison operators are a closed
whitelist below.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel


_OPERATORS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "contains": lambda a, b: (b is not None and a is not None and str(b).lower() in str(a).lower()),
    "in": lambda a, b: a in b,
}


class Operation(BaseModel):
    op: Literal["filter", "count", "group_by_count", "sort", "top_n", "distinct"]
    field: Optional[str] = None
    operator: Optional[Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "in"]] = None
    value: Optional[Any] = None
    descending: bool = False
    n: Optional[int] = None


def _get_field(item: dict, field: str) -> Any:
    # supports simple dotted paths, e.g. "flavor.original_name"
    cur: Any = item
    for part in field.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def apply_operation(data: list[dict], operation: Operation) -> Any:
    if operation.op == "filter":
        if not operation.field or not operation.operator:
            raise ValueError("filter requires 'field' and 'operator'")
        cmp = _OPERATORS[operation.operator]
        return [item for item in data if cmp(_get_field(item, operation.field), operation.value)]

    if operation.op == "count":
        return {"count": len(data)}

    if operation.op == "group_by_count":
        if not operation.field:
            raise ValueError("group_by_count requires 'field'")
        counts: dict[str, int] = {}
        for item in data:
            key = str(_get_field(item, operation.field))
            counts[key] = counts.get(key, 0) + 1
        return counts

    if operation.op == "sort":
        if not operation.field:
            raise ValueError("sort requires 'field'")
        return sorted(
            data,
            key=lambda item: (_get_field(item, operation.field) is None, _get_field(item, operation.field)),
            reverse=operation.descending,
        )

    if operation.op == "top_n":
        n = operation.n or 10
        return data[:n]

    if operation.op == "distinct":
        if not operation.field:
            raise ValueError("distinct requires 'field'")
        seen = []
        for item in data:
            val = _get_field(item, operation.field)
            if val not in seen:
                seen.append(val)
        return seen

    raise ValueError(f"unsupported operation: {operation.op}")
