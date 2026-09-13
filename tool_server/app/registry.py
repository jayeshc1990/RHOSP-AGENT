"""
Strict allow-list of readable OpenStack resource types.

SECURITY: this registry is the only thing standing between a user/LLM-supplied
`resource_type` string and an actual openstacksdk method call. We deliberately do
NOT do `getattr(proxy, resource_type)` on arbitrary input - that would let any
string that happens to match a real SDK method name (including a mutating one)
execute. Instead every entry here is a literal, hand-reviewed tuple of
(service_proxy_attr, list_method_name, get_method_name_or_None) that has been
confirmed to be read-only.

Extending this file:
  - Only add `list`-style methods (they return generators of resources, and map
    to a GET on the OpenStack API) and `get_*` / `find_*` methods for single
    lookups.
  - NEVER add anything named create_*, update_*, delete_*, add_*, remove_*,
    reset_*, migrate_*, reboot_*, resize_*, backup_* (action), restore_*, etc.
  - When in doubt, check the method in the openstacksdk docs and confirm it
    issues a GET request before adding it here.
"""

from typing import NamedTuple, Optional


class ResourceSpec(NamedTuple):
    service: str            # attribute on the openstack.connection.Connection, e.g. "compute"
    list_method: str        # method name that returns an iterable of resources (a GET/list call)
    get_method: Optional[str]  # method name for a single lookup by id (a GET/show call), if available


REGISTRY: dict[str, ResourceSpec] = {
    # Compute (Nova)
    "servers": ResourceSpec("compute", "servers", "get_server"),
    "flavors": ResourceSpec("compute", "flavors", "get_flavor"),
    "hypervisors": ResourceSpec("compute", "hypervisors", "get_hypervisor"),
    "compute_availability_zones": ResourceSpec("compute", "availability_zones", None),
    "keypairs": ResourceSpec("compute", "keypairs", "get_keypair"),
    "server_groups": ResourceSpec("compute", "server_groups", "get_server_group"),

    # Networking (Neutron)
    "networks": ResourceSpec("network", "networks", "get_network"),
    "subnets": ResourceSpec("network", "subnets", "get_subnet"),
    "ports": ResourceSpec("network", "ports", "get_port"),
    "routers": ResourceSpec("network", "routers", "get_router"),
    "security_groups": ResourceSpec("network", "security_groups", "get_security_group"),
    "security_group_rules": ResourceSpec("network", "security_group_rules", "get_security_group_rule"),
    "floating_ips": ResourceSpec("network", "ips", "get_ip"),
    "network_agents": ResourceSpec("network", "agents", "get_agent"),

    # Block Storage (Cinder)
    "volumes": ResourceSpec("block_storage", "volumes", "get_volume"),
    "volume_snapshots": ResourceSpec("block_storage", "snapshots", "get_snapshot"),
    "volume_backups": ResourceSpec("block_storage", "backups", "get_backup"),
    "volume_types": ResourceSpec("block_storage", "types", None),

    # Image (Glance)
    "images": ResourceSpec("image", "images", "get_image"),

    # Identity (Keystone) - metadata only, no secrets
    "projects": ResourceSpec("identity", "projects", "get_project"),
    "domains": ResourceSpec("identity", "domains", "get_domain"),
    "users": ResourceSpec("identity", "users", "get_user"),

    # Orchestration (Heat) - present on some RHOSP deployments
    "stacks": ResourceSpec("orchestration", "stacks", "get_stack"),
}


def allowed_resource_types() -> list[str]:
    return sorted(REGISTRY.keys())
