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
    "compute_services": ResourceSpec("compute", "services", None),  # `openstack compute service list`
    "migrations": ResourceSpec("compute", "migrations", None),  # cloud-wide live/cold migration history
    # NOT added: server_migrations() - requires a specific server as a positional
    # arg (per-server scoped), doesn't fit this registry's flat "list everything,
    # optionally filter" shape. Same reasoning applies throughout this file for
    # anything else that's scoped to a specific parent resource rather than
    # listable on its own.

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
    "volume_services": ResourceSpec("block_storage", "services", None),  # `openstack volume service list`

    # Image (Glance)
    "images": ResourceSpec("image", "images", "get_image"),

    # Identity (Keystone) - metadata only, no secrets
    "projects": ResourceSpec("identity", "projects", "get_project"),
    "domains": ResourceSpec("identity", "domains", "get_domain"),
    "users": ResourceSpec("identity", "users", "get_user"),

    # Orchestration (Heat) - present on some RHOSP deployments
    "stacks": ResourceSpec("orchestration", "stacks", "get_stack"),

    # Load Balancing (Octavia) - present on some RHOSP deployments
    "load_balancers": ResourceSpec("load_balancer", "load_balancers", "get_load_balancer"),
    "load_balancer_listeners": ResourceSpec("load_balancer", "listeners", "get_listener"),
    "load_balancer_pools": ResourceSpec("load_balancer", "pools", "get_pool"),

    # Bare Metal (Ironic) - present on some RHOSP deployments
    "baremetal_nodes": ResourceSpec("baremetal", "nodes", "get_node"),
    "baremetal_ports": ResourceSpec("baremetal", "ports", "get_port"),
    "baremetal_chassis": ResourceSpec("baremetal", "chassis", "get_chassis"),

    # Shared File Systems / Manila - present on some RHOSP deployments
    "shares": ResourceSpec("shared_file_system", "shares", "get_share"),
    "share_networks": ResourceSpec("shared_file_system", "share_networks", "get_share_network"),
    "share_snapshots": ResourceSpec("shared_file_system", "share_snapshots", "get_share_snapshot"),
    "share_types": ResourceSpec("shared_file_system", "share_types", "get_share_type"),
    "share_instances": ResourceSpec("shared_file_system", "share_instances", "get_share_instance"),
    "share_groups": ResourceSpec("shared_file_system", "share_groups", "get_share_group"),
    "share_group_snapshots": ResourceSpec("shared_file_system", "share_group_snapshots", "get_share_group_snapshot"),
    "storage_pools": ResourceSpec("shared_file_system", "storage_pools", None),
    # NOT added: access_rules() - requires a specific share as a positional arg.

    # DNS (Designate) - present on some RHOSP deployments
    "dns_zones": ResourceSpec("dns", "zones", "get_zone"),
    "dns_recordsets": ResourceSpec("dns", "recordsets", "get_recordset"),

    # Placement - scheduling/capacity accounting, usually present alongside Nova
    "resource_providers": ResourceSpec("placement", "resource_providers", "get_resource_provider"),
    "resource_classes": ResourceSpec("placement", "resource_classes", "get_resource_class"),

    # Key Manager (Barbican) - present on some RHOSP deployments. Lists secret
    # METADATA only (name, id, status, expiration, content type) - nothing here
    # ever fetches a secret's actual decrypted payload, that's a separate
    # action this registry deliberately does not wire up.
    "secrets": ResourceSpec("key_manager", "secrets", "get_secret"),
    "secret_containers": ResourceSpec("key_manager", "containers", "get_container"),

    # Object Store (Swift) - present on some RHOSP deployments. Only container-
    # level listing (names, object counts, sizes) - see the note below on why
    # object-level listing/download isn't included the same way.
    "object_containers": ResourceSpec("object_store", "containers", None),
    # NOT added: objects() - requires a specific container as a positional arg
    # (same "scoped to a parent" shape as access_rules/server_migrations above).
    # NOT added: get_object() - unlike every other get_method in this file, it
    # doesn't return a Resource with .to_dict() - it downloads actual object
    # content (potentially large binary data), a fundamentally different
    # operation from every other "fetch one resource's metadata" call here.
}


def allowed_resource_types() -> list[str]:
    return sorted(REGISTRY.keys())


# Common natural-language terms mapped to the canonical REGISTRY key. A model
# knows "compute nodes"/"load balancers" as domain terms, not necessarily the
# exact internal key ("hypervisors"/"load_balancers") - resolve common phrasings
# instead of erroring on a technically-valid but differently-spelled request.
RESOURCE_TYPE_ALIASES: dict[str, str] = {
    "vm": "servers",
    "vms": "servers",
    "instance": "servers",
    "instances": "servers",
    "compute_node": "hypervisors",
    "compute_nodes": "hypervisors",
    "computenode": "hypervisors",
    "computenodes": "hypervisors",
    "host": "hypervisors",
    "hosts": "hypervisors",
    "loadbalancer": "load_balancers",
    "loadbalancers": "load_balancers",
    "lb": "load_balancers",
    "lbs": "load_balancers",
    "disk": "volumes",
    "disks": "volumes",
    "snapshot": "volume_snapshots",
    "snapshots": "volume_snapshots",
    "backup": "volume_backups",
    "backups": "volume_backups",
    "flavor": "flavors",
    "image": "images",
    "network": "networks",
    "subnet": "subnets",
    "port": "ports",
    "router": "routers",
    "securitygroup": "security_groups",
    "securitygroups": "security_groups",
    "floatingip": "floating_ips",
    "floatingips": "floating_ips",
    "project": "projects",
    "tenant": "projects",
    "tenants": "projects",
    "domain": "domains",
    "user": "users",
    "stack": "stacks",
    "compute_service": "compute_services",
    "computeservices": "compute_services",
    "computeservice": "compute_services",
    "nova_services": "compute_services",
    "novaservices": "compute_services",
    "volume_service": "volume_services",
    "volumeservices": "volume_services",
    "volumeservice": "volume_services",
    "cinder_services": "volume_services",
    "cinderservices": "volume_services",
    "migration": "migrations",
    "baremetal_node": "baremetal_nodes",
    "baremetalnodes": "baremetal_nodes",
    "ironic_nodes": "baremetal_nodes",
    "baremetal_port": "baremetal_ports",
    "baremetalports": "baremetal_ports",
    "baremetal_chassi": "baremetal_chassis",
    "share": "shares",
    "share_network": "share_networks",
    "sharenetworks": "share_networks",
    "share_snapshot": "share_snapshots",
    "sharesnapshots": "share_snapshots",
    "share_type": "share_types",
    "sharetypes": "share_types",
    "share_instance": "share_instances",
    "share_group": "share_groups",
    "sharegroups": "share_groups",
    "share_group_snapshot": "share_group_snapshots",
    "storage_pool": "storage_pools",
    "storagepools": "storage_pools",
    "zone": "dns_zones",
    "zones": "dns_zones",
    "dnszones": "dns_zones",
    "recordset": "dns_recordsets",
    "recordsets": "dns_recordsets",
    "dnsrecordsets": "dns_recordsets",
    "resource_provider": "resource_providers",
    "resourceproviders": "resource_providers",
    "resource_class": "resource_classes",
    "resourceclasses": "resource_classes",
    "secret": "secrets",
    "secret_container": "secret_containers",
    "secretcontainers": "secret_containers",
    "container": "object_containers",
    "containers": "object_containers",
    "object_container": "object_containers",
    "objectcontainers": "object_containers",
    "bucket": "object_containers",
    "buckets": "object_containers",
}


def resolve_resource_type(name: str) -> str:
    """Normalize a caller-supplied resource type to its canonical REGISTRY key,
    via RESOURCE_TYPE_ALIASES if it's a recognized alias, else unchanged
    (REGISTRY lookups elsewhere still validate it and reject anything unknown -
    this only widens what counts as a valid *spelling* of a real entry)."""
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    return RESOURCE_TYPE_ALIASES.get(key, key)


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
    "compute_services": ["id", "binary", "host", "status", "state", "zone"],
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
    "volume_services": ["id", "binary", "host", "status", "state", "zone"],
    "images": ["id", "name", "status", "disk_format", "size"],
    "projects": ["id", "name", "domain_id", "enabled"],
    "domains": ["id", "name", "enabled"],
    "users": ["id", "name", "domain_id", "enabled"],
    "stacks": ["id", "stack_name", "stack_status"],
    "load_balancers": ["id", "name", "provisioning_status", "operating_status", "vip_address"],
    "load_balancer_listeners": ["id", "name", "protocol", "protocol_port", "provisioning_status"],
    "load_balancer_pools": ["id", "name", "protocol", "lb_algorithm", "provisioning_status"],
    "migrations": ["id", "status", "source_compute", "dest_compute", "migration_type"],
    "baremetal_nodes": ["id", "name", "power_state", "provision_state", "maintenance"],
    "baremetal_ports": ["id", "address", "node_id", "pxe_enabled"],
    "baremetal_chassis": ["id", "description"],
    "shares": ["id", "name", "status", "size", "share_proto", "project_id"],
    "share_networks": ["id", "name", "status"],
    "share_snapshots": ["id", "name", "status", "share_id", "size"],
    "share_types": ["id", "name"],
    "share_instances": ["id", "status", "share_id", "host"],
    "share_groups": ["id", "name", "status"],
    "share_group_snapshots": ["id", "name", "status", "share_group_id"],
    "storage_pools": ["name", "host", "backend", "pool"],
    "dns_zones": ["id", "name", "status", "type"],
    "dns_recordsets": ["id", "name", "type", "records", "status"],
    "resource_providers": ["id", "name", "generation"],
    "resource_classes": ["name"],
    "secrets": ["secret_ref", "name", "status", "content_types", "expiration"],
    "secret_containers": ["container_ref", "name", "type", "status"],
    "object_containers": ["name", "count", "bytes"],
}

_DEFAULT_SUMMARY_FIELDS = ["id", "name", "status"]


def summarize_item(item: dict, resource_type: str) -> dict:
    fields = SUMMARY_FIELDS.get(resource_type, _DEFAULT_SUMMARY_FIELDS)
    return {k: item[k] for k in fields if k in item}
