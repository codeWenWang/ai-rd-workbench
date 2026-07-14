import re


def render_architecture(files, relations) -> str:
    lines = ["flowchart LR"]
    node_ids = {item.relative_path: _node_id(item.relative_path) for item in files}
    for item in files:
        lines.append(f'    {node_ids[item.relative_path]}["{_label(item.relative_path)}"]')
    for index, relation in enumerate(relations):
        source = node_ids.get(relation.source_path)
        if not source:
            continue
        target = f"external_{index}"
        style = "-.->" if relation.inferred else "-->"
        lines.append(f'    {target}["{_label(relation.target)}"]')
        lines.append(f"    {source} {style}|{relation.kind}| {target}")
    return "\n".join(lines)


def render_flow(files, routes, relations) -> str:
    file_paths = {item.id: item.relative_path for item in files}
    lines = ["flowchart TD", '    client["客户端请求"]']
    for index, route in enumerate(routes):
        route_id = f"route_{index}"
        handler_id = f"handler_{index}"
        location = file_paths.get(route.project_file_id, "unknown")
        lines.append(f'    {route_id}["{route.method} {_label(route.path)}"]')
        lines.append(f'    {handler_id}["{_label(route.handler)} · {_label(location)}:{route.line_number}"]')
        lines.append(f"    client --> {route_id} --> {handler_id}")
        for relation_index, relation in enumerate(
            item for item in relations if item.source_path == location and item.kind == "call"
        ):
            call_id = f"call_{index}_{relation_index}"
            lines.append(f'    {call_id}["{_label(relation.target)} · 推断"]')
            lines.append(f"    {handler_id} -.-> {call_id}")
    if not routes:
        lines.append('    client --> empty["未识别到 FastAPI 路由"]')
    return "\n".join(lines)


def render_sequence(files, routes, relations) -> str:
    file_paths = {item.id: item.relative_path for item in files}
    lines = ["sequenceDiagram", "    participant U as 用户", "    participant API as API"]
    for index, route in enumerate(routes):
        handler = f"H{index}"
        location = file_paths.get(route.project_file_id, "unknown")
        lines.append(f"    participant {handler} as {_label(route.handler)}")
        lines.append(f"    U->>API: {route.method} {_label(route.path)}")
        lines.append(f"    API->>{handler}: {_label(location)}:{route.line_number}")
        for relation in (
            item for item in relations if item.source_path == location and item.kind == "call"
        ):
            lines.append(f"    Note over {handler}: 推断调用 {_label(relation.target)}")
        lines.append(f"    {handler}-->>API: 返回结果")
        lines.append("    API-->>U: HTTP 响应")
    if not routes:
        lines.append("    Note over U,API: 未识别到 FastAPI 路由")
    return "\n".join(lines)


def _node_id(value: str) -> str:
    return "node_" + re.sub(r"[^A-Za-z0-9_]", "_", value)


def _label(value: str) -> str:
    return str(value).replace('"', "'").replace("\n", " ")
