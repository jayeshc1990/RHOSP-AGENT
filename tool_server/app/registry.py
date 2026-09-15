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


# Curated top-level fields kept when summarizing a resource for a plain listing
# page (GET /resources/{type} with no `operation`). A full server dict alone
# can easily run 500-1000+ tokens (security_groups, tags, metadata, OS-EXT-*
# attributes, image, host info, ...) - way too much for a human-facing list of
# even a few dozen items. This is display-only pruning: the `operation` path in
# main.py runs against the full (lightly-compacted, not summarized) data, so
# filter/count/group-by results stay accurate across any field, not just the
# ones listed here.
SUMMARY_FIELDS: dict[str, list[str]] = {
    "servers": ["id", "name", "status", "flavor", "addresses", "created_at", "project_id"],
    "flavors": ["id", "name", "vcpus", "ram", "disk"],
    "hypervisors": ["id", "name", "status", "state"],
    "compute_availability_zones": ["name", "state"],
    "keypairs": ["name", "fingerprint", "type"],
    "server_groups": ["id", "name", "policies"],
    "networks": ["id", "name", "status", "is_shared", "subnet_ids"],
    "subnets": ["id", "name", "cidr", "network_id"],
    "ports": ["id", "name", "status", "fixed_ips", "device_id"],
    "routers": ["id", "name", "status"],
    "security_groups": ["id", "name", "description"],
    "security_group_rules": ["id", "protocol", "direction", "port_range_min", "port_range_max"],
    "floating_ips": ["id", "floating_ip_address", "status", "port_id"],
    "network_agents": ["id", "agent_type", "host", "alive", "admin_state_up"],
    "volumes": ["id", "name", "status", "size", "volume_type"],
    "volume_snapshots": ["id", "name", "status", "volume_id", "size"],
    "volume_backups": ["id", "name", "status", "volume_id", "size"],
    "volume_types": ["id", "name"],
    "images": ["id", "name", "status", "disk_format", "size"],
    "projects": ["id", "name", "domain_id", "enabled"],
    "domains": ["id", "name", "enabled"],
    "users": ["id", "name", "domain_id", "enabled"],
    "stacks": ["id", "stack_name", "stack_status"],
}

_DEFAULT_SUMMARY_FIELDS = ["id", "name", "status"]


def summarize_item(item: dict, resource_type: str) -> dict:
    fields = SUMMARY_FIELDS.get(resource_type, _DEFAULT_SUMMARY_FIELDS)
    return {k: item[k] for k in fields if k in item}
