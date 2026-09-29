from __future__ import annotations

from typing import Any


def chat_tool_schemas(request: Any, *, graph_available: bool = False) -> list[dict[str, Any]]:
    def tool(name: str, description: str, properties: dict[str, Any], required: list[str]):
        return {"type": "function", "function": {"name": name, "description": description,
                "parameters": {"type": "object", "properties": properties, "required": required,
                               "additionalProperties": False}}}

    query = {"query": {"type": "string", "minLength": 1, "maxLength": 2000}}
    tools = [
        tool("calculator", "精确计算算术和大整数。使用对话中已明确的变量，不允许猜值。", {
            "expression": {"type": "string", "maxLength": 2048},
            "variables": {"type": "object", "additionalProperties": {"type": "string"}},
        }, ["expression"]),
        tool("search_knowledge", "查询当前项目知识库中的资料。", query, ["query"]),
    ]
    if request.config.allow_web_search:
        tools.append(tool("search_web", "搜索互联网并读取可核验的来源。天气、最新信息、完整作品列表等必须先查询；返回空或错误不代表未配置此工具。", query, ["query"]))
    if graph_available:
        tools.append(tool("search_graph", "查询当前项目中的实体关系。", query, ["query"]))
    return [item for item in tools if item["function"]["name"] not in request.config.disabled_tools]
