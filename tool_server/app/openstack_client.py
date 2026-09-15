"""
Multi-cloud connection factory over openstacksdk, restricted to the resource
types in registry.REGISTRY. Reads standard clouds.yaml (OS_CLIENT_CONFIG_FILE
env var, or the current directory / ~/.config/openstack by SDK default).
"""

import functools
import os

import openstack
import yaml

from .registry import REGISTRY


class UnknownCloudError(Exception):
    pass


class UnknownResourceTypeError(Exception):
    pass


class ResourceHasNoGetError(Exception):
    pass


_CLOUDS_YAML_SEARCH_PATHS = [
    os.environ.get("OS_CLIENT_CONFIG_FILE"),
    "clouds.yaml",
    os.path.expanduser("~/.config/openstack/clouds.yaml"),
    "/etc/openstack/clouds.yaml",
]


def _find_clouds_yaml() -> str | None:
    for path in _CLOUDS_YAML_SEARCH_PATHS:
        if path and os.path.isfile(path):
            return path
    return None


def list_configured_clouds() -> list[str]:
    # Deliberately does NOT use openstack.config.loader's get_all()/get_one(),
    # which fully instantiate an auth plugin (and validate every required auth
    # field) for EVERY cloud just to read their names - one incomplete or
    # placeholder cloud entry anywhere in clouds.yaml would then break listing
    # every cloud, including working ones. Just read the names directly.
    path = _find_clouds_yaml()
    if not path:
        return []
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return sorted((data.get("clouds") or {}).keys())


@functools.lru_cache(maxsize=32)
def _get_connection(cloud: str) -> "openstack.connection.Connection":
    if cloud not in list_configured_clouds():
        raise UnknownCloudError(f"cloud '{cloud}' is not defined in clouds.yaml")
    # openstack.connect() only ever issues the calls we make on the returned
    # proxies below - it does not itself perform any mutating setup calls.
    return openstack.connect(cloud=cloud)


# Fields dropped from every resource dict when compact=True (the default).
# These are SDK-internal bookkeeping or link/reference noise that eats tokens
# without being useful to the model - not resource data itself. None-valued
# fields are also dropped, since OpenStack resource dicts have dozens of
# optional fields that are usually unset.
_COMPACT_DROP_KEYS = {"links", "location"}


def _compact_item(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in _COMPACT_DROP_KEYS and v is not None}


def list_resources(
    cloud: str, resource_type: str, filters: dict | None = None, compact: bool = True
) -> list[dict]:
    if resource_type not in REGISTRY:
        raise UnknownResourceTypeError(
            f"'{resource_type}' is not a readable resource type. "
            f"Allowed: {sorted(REGISTRY.keys())}"
        )
    spec = REGISTRY[resource_type]
    conn = _get_connection(cloud)
    service_proxy = getattr(conn, spec.service)
    list_fn = getattr(service_proxy, spec.list_method)
    # openstacksdk list methods accept **query kwargs, which become GET query
    # string parameters against the OpenStack API - still a read-only call.
    results = list_fn(**(filters or {}))
    dicts = [r.to_dict() for r in results]
    if compact:
        dicts = [_compact_item(d) for d in dicts]
    return dicts


def get_resource(cloud: str, resource_type: str, resource_id: str) -> dict:
    if resource_type not in REGISTRY:
        raise UnknownResourceTypeError(
            f"'{resource_type}' is not a readable resource type. "
            f"Allowed: {sorted(REGISTRY.keys())}"
        )
    spec = REGISTRY[resource_type]
    if not spec.get_method:
        raise ResourceHasNoGetError(
            f"'{resource_type}' does not support single-item lookup; use list_resources with a filter."
        )
    conn = _get_connection(cloud)
    service_proxy = getattr(conn, spec.service)
    get_fn = getattr(service_proxy, spec.get_method)
    result = get_fn(resource_id)
    return result.to_dict()
