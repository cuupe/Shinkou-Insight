from __future__ import annotations

from typing import Any


class GraphSearchTool:
    """Tenant-scoped graph adapter exposed through the common tool registry."""

    def __init__(self, graph_store: Any):
        self.graph_store = graph_store

    async def search_graph(
        self,
        *,
        workspace_id: int,
        project_id: int,
        query: str,
        limit: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        nodes, relationships = await self.graph_store.search(
            workspace_id=workspace_id,
            project_id=project_id,
            query=query,
            limit=max(1, min(int(limit), 50)),
        )
        return {
            "nodes": [_node_payload(node) for node in nodes],
            "relationships": [_relationship_payload(edge) for edge in relationships],
        }


def _node_payload(node: Any) -> dict[str, Any]:
    return {
        "key": str(getattr(node, "key", "")),
        "name": str(getattr(node, "name", "")),
        "nodeType": str(getattr(node, "node_type", "ENTITY")),
        "workspaceId": getattr(node, "workspace_id", None),
        "projectId": getattr(node, "project_id", None),
        "properties": dict(getattr(node, "properties", {}) or {}),
    }


def _relationship_payload(edge: Any) -> dict[str, Any]:
    return {
        "source": str(getattr(edge, "source", "")),
        "target": str(getattr(edge, "target", "")),
        "relation": str(getattr(edge, "relation", "RELATED_TO")),
        "workspaceId": getattr(edge, "workspace_id", None),
        "projectId": getattr(edge, "project_id", None),
        "properties": dict(getattr(edge, "properties", {}) or {}),
    }
