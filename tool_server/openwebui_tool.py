"""
title: RHOSP Agent Read-Only Tools
author: RHOSP Agent
description: Read-only query tools over RHOSP OpenStack clouds via the tool_server API.
version: 0.1.0
"""

import json

import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        TOOL_SERVER_BASE_URL: str = Field(
            default="http://tool-server:8080",
            description="Base URL of the RHOSP Agent tool_server (container hostname on the compose network).",
        )

    def __init__(self):
        self.valves = self.Valves()

    def list_clouds(self) -> str:
        """
        List every OpenStack cloud this agent can query.
        """
        r = requests.get(f"{self.valves.TOOL_SERVER_BASE_URL}/clouds", timeout=30)
        r.raise_for_status()
        return r.text

    def list_resource_types(self) -> str:
        """
        List every resource type that can be queried (servers, networks, volumes, etc).
        """
        r = requests.get(f"{self.valves.TOOL_SERVER_BASE_URL}/resource-types", timeout=30)
        r.raise_for_status()
        return r.text

    def list_resources(
        self,
        cloud: str,
        resource_type: str,
        name: str = "",
        status: str = "",
        project_id: str = "",
    ) -> str:
        """
        List resources of a given type on a given cloud, optionally filtered by name, status, or project_id.

        :param cloud: Cloud name, from list_clouds.
        :param resource_type: Resource type, from list_resource_types (e.g. "servers", "networks", "volumes").
        :param name: Optional exact-name filter.
        :param status: Optional status filter.
        :param project_id: Optional owning-project filter.
        """
        params = {"cloud": cloud}
        if name:
            params["name"] = name
        if status:
            params["status"] = status
        if project_id:
            params["project_id"] = project_id
        r = requests.get(
            f"{self.valves.TOOL_SERVER_BASE_URL}/resources/{resource_type}",
            params=params,
            timeout=60,
        )
        r.raise_for_status()
        return r.text

    def get_resource(self, cloud: str, resource_type: str, resource_id: str) -> str:
        """
        Get a single resource by id.

        :param cloud: Cloud name, from list_clouds.
        :param resource_type: Resource type, from list_resource_types.
        :param resource_id: The resource's id.
        """
        r = requests.get(
            f"{self.valves.TOOL_SERVER_BASE_URL}/resources/{resource_type}/{resource_id}",
            params={"cloud": cloud},
            timeout=30,
        )
        r.raise_for_status()
        return r.text

    def analyze(self, data_json: str, operation_json: str) -> str:
        """
        Deterministically filter/count/group/sort data already fetched via list_resources.
        Use this instead of counting or filtering a large list yourself - it does not call
        OpenStack, it only processes data you already fetched.

        :param data_json: JSON array string of the resource list to analyze (the exact output of list_resources).
        :param operation_json: JSON object string describing the operation, e.g.
            {"op": "count"} or
            {"op": "filter", "field": "flavor.original_name", "operator": "eq", "value": "m1.small"} or
            {"op": "group_by_count", "field": "status"} or
            {"op": "sort", "field": "name"} or
            {"op": "top_n", "n": 5} or
            {"op": "distinct", "field": "status"}.
        """
        payload = {"data": json.loads(data_json), "operation": json.loads(operation_json)}
        r = requests.post(f"{self.valves.TOOL_SERVER_BASE_URL}/analyze", json=payload, timeout=30)
        r.raise_for_status()
        return r.text
