"""
Multi-cloud connection factory over openstacksdk, restricted to the resource
types in registry.REGISTRY. Reads standard clouds.yaml (OS_CLIENT_CONFIG_FILE
env var, or the current directory / ~/.config/openstack by SDK default).
"""

import functools
import os

import openstack
from openstack.config import loader as config_loader

from .registry import REGISTRY


class UnknownCloudError(Exception):
    pass


class UnknownResourceTypeError(Exception):
    pass


class ResourceHasNoGetError(Exception):
    pass


def list_configured_clouds() -> list[str]:
    config = config_loader.OpenStackConfig()
    return sorted(c.name for c in config.get_all())


@functools.lru_cache(maxsize=32)
def _get_connection(cloud: str) -> "openstack.connection.Connection":
    if cloud not in list_configured_clouds():
        raise UnknownCloudError(f"cloud '{cloud}' is not defined in clouds.yaml")
    # openstack.connect() only ever issues the calls we make on the returned
    # proxies below - it does not itself perform any mutating setup calls.
    return openstack.connect(cloud=cloud)


def list_resources(cloud: str, resource_type: str, filters: dict | None = None) -> list[dict]:
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
    return [r.to_dict() for r in results]


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
