"""
Read-only OpenStack tool server.

Exposes a small OpenAPI surface that Open WebUI (or any OpenAPI-tool-capable
chat client / MCP bridge) can import directly as tools:

  GET  /clouds                                  - list configured clouds
  GET  /resource-types                          - list readable resource types
  GET  /resources/{resource_type}                - list resources (with optional filters,
                                                    and an optional server-side operation -
                                                    see below)
  GET  /resources/{resource_type}/{resource_id}  - get a single resource
  POST /analyze                                  - deterministic filter/count/group/sort
                                                    over data already fetched (not an
                                                    OpenStack call - see analyze.py)

IMPORTANT on large result sets: GET /resources/{resource_type} always fetches
the FULL matching set from OpenStack internally (needed for an accurate count
or filter), but only returns a capped page of full records by default (see
`limit`) - dumping hundreds of raw resource dicts into an LLM's context both
wastes tokens and risks exceeding it entirely. For "how many X" or "X matching
Y" questions on a potentially large result set, pass `operation` (the same
JSON shape POST /analyze takes) instead of fetching everything and analyzing
it client-side - the operation runs here, server-side, against the full set,
and only the small final result (a count, a short filtered list, etc.) is
returned - the raw full set never has to pass through the model's context.

Every call that reaches OpenStack goes through registry.REGISTRY, which only
contains list/get methods - see registry.py for the security rationale. The
OpenStack-side identity used here should ALWAYS be an application credential
scoped to the `reader` role (see ../README.md), so even a bug here cannot
mutate anything - Keystone/Nova/Neutron/etc. will reject it with 403.
"""

import json
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from . import openstack_client as osc
from .analyze import Operation, apply_operation
from .registry import allowed_resource_types, summarize_item

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rhosp-agent-tool-server")

app = FastAPI(
    title="RHOSP Agent Tool Server",
    description="Read-only query tools over multiple RHOSP clouds.",
    version="0.1.0",
)


@app.get("/clouds", summary="List every OpenStack cloud this agent can query")
def get_clouds() -> list[str]:
    return osc.list_configured_clouds()


@app.get("/resource-types", summary="List every resource type that can be queried")
def get_resource_types() -> list[str]:
    return allowed_resource_types()


@app.get(
    "/resources/{resource_type}",
    summary="List resources of a given type on a given cloud, optionally filtered, "
    "counted, or analyzed server-side",
)
def get_resources(
    resource_type: str,
    cloud: str = Query(..., description="Cloud name, from GET /clouds"),
    name: Optional[str] = Query(None, description="Filter by exact name, if supported by the resource"),
    status: Optional[str] = Query(None, description="Filter by status, if supported by the resource"),
    project_id: Optional[str] = Query(None, description="Filter by owning project id, if supported"),
    compact: bool = Query(
        True,
        description="Drop link/internal-bookkeeping fields and null-valued fields to save tokens. "
        "Set false only if you need full raw detail on every item.",
    ),
    limit: int = Query(
        50,
        description="Max full records to return in `results` when `operation` is not given. "
        "`total_count` is always the TRUE total regardless of this cap - use it, not "
        "len(results), when the user just wants a count.",
    ),
    operation: Optional[str] = Query(
        None,
        description="JSON-encoded operation (same shape as POST /analyze's `operation` field) "
        "to run server-side against the FULL result set before responding, e.g. "
        '\'{"op":"count"}\' or \'{"op":"filter","field":"flavor.original_name",'
        '"operator":"eq","value":"m1.small"}\'. Use this instead of fetching everything '
        "and filtering/counting it yourself - it avoids sending a potentially huge raw "
        "list through your own context, and the result is exact since it runs against "
        "every matching record, not just the capped page `limit` would otherwise return.",
    ),
) -> dict:
    filters = {k: v for k, v in {"name": name, "status": status, "project_id": project_id}.items() if v}
    try:
        logger.info("list_resources cloud=%s type=%s filters=%s compact=%s", cloud, resource_type, filters, compact)
        full = osc.list_resources(cloud, resource_type, filters, compact=compact)
    except osc.UnknownCloudError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except osc.UnknownResourceTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if operation:
        try:
            op = Operation(**json.loads(operation))
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"invalid operation: {e}")
        try:
            return {"result": apply_operation(full, op)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    page = full[:limit]
    return {
        "total_count": len(full),
        "returned_count": len(page),
        "results": [summarize_item(item, resource_type) for item in page],
        "note": "results is trimmed to a few key fields per item to save tokens - "
        "use get_resource for full detail on one specific item.",
    }


@app.get(
    "/resources/{resource_type}/{resource_id}",
    summary="Get a single resource by id",
)
def get_resource(resource_type: str, resource_id: str, cloud: str = Query(...)) -> dict:
    try:
        logger.info("get_resource cloud=%s type=%s id=%s", cloud, resource_type, resource_id)
        return osc.get_resource(cloud, resource_type, resource_id)
    except osc.UnknownCloudError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (osc.UnknownResourceTypeError, osc.ResourceHasNoGetError) as e:
        raise HTTPException(status_code=400, detail=str(e))


class AnalyzeRequest(BaseModel):
    data: list[dict]
    operation: Operation


@app.post(
    "/analyze",
    summary="Deterministically filter/count/group/sort data already fetched via /resources "
    "(this endpoint does not call OpenStack)",
)
def post_analyze(req: AnalyzeRequest):
    try:
        return apply_operation(req.data, req.operation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}
