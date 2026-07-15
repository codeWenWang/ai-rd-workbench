import re


def render_architecture(insight) -> str:
    lines = ["flowchart LR"]
    if not insight.modules:
        lines.append('    project["当前静态分析未识别到可聚合模块"]')
        return "\n".join(lines)
    for module in insight.modules:
        module_id = _node_id(module.name)
        languages = " / ".join(module.languages[:3]) or "待识别"
        lines.append(
            f'    {module_id}["{_label(module.name)}<br/>{_label(module.role)} · {_label(languages)} · {module.file_count} 文件"]'
        )
    module_names = {module.name for module in insight.modules}
    for module in insight.modules:
        for dependency in module.dependencies:
            if dependency in module_names:
                lines.append(f"    {_node_id(module.name)} --> {_node_id(dependency)}")
    return "\n".join(lines)


def render_flow(insight) -> str:
    lines = ["flowchart TD", '    client["客户端 / 调用方"]']
    endpoint = _representative_endpoint(insight)
    modules = {module.name: module for module in insight.modules}
    if endpoint:
        entry_id = "entry"
        handler_id = "handler"
        lines.append(
            f'    {entry_id}["{_label(endpoint.framework)} · {endpoint.method} {_label(endpoint.path)}"]'
        )
        lines.append(
            f'    {handler_id}["{_label(endpoint.handler)}<br/>{_label(endpoint.source_path)}:{endpoint.line_number}"]'
        )
        lines.append(f"    client --> {entry_id} --> {handler_id}")
        dependency_nodes = []
        for index, module_name in enumerate(_relevant_dependencies(endpoint, modules)):
            module = modules[module_name]
            node_id = f"step_{index}_{_node_id(module_name)}"
            lines.append(f'    {node_id}["{_label(module.name)} · {_label(module.role)}"]')
            lines.append(f"    {handler_id} --> {node_id}")
            dependency_nodes.append(node_id)
        lines.append('    response["返回响应"]')
        if dependency_nodes:
            for node_id in dependency_nodes:
                lines.append(f"    {node_id} -.-> response")
        else:
            lines.append(f"    {handler_id} --> response")
    elif insight.modules:
        ordered = _ordered_modules(insight.modules)
        previous = "client"
        for index, module in enumerate(ordered[:8]):
            node_id = f"module_{index}_{_node_id(module.name)}"
            lines.append(f'    {node_id}["{_label(module.name)} · {_label(module.role)}"]')
            lines.append(f"    {previous} --> {node_id}")
            previous = node_id
        lines.append('    note["当前静态分析未识别到可验证接口，展示模块主链路"]')
        lines.append(f"    {previous} -.-> note")
    else:
        lines.append('    client --> empty["当前静态分析未识别到可验证流程"]')
    return "\n".join(lines)


def render_sequence(insight) -> str:
    endpoint = _representative_endpoint(insight)
    modules = {module.name: module for module in insight.modules}
    lines = ["sequenceDiagram", "    participant U as 客户端"]
    if endpoint:
        entry = _participant_id(endpoint.module or "application")
        handler = "H"
        lines.append(f"    participant {entry} as {_label(endpoint.module)} · {_label(endpoint.framework)}")
        lines.append(f"    participant {handler} as {_label(endpoint.handler)}")
        lines.append(f"    U->>{entry}: {endpoint.method} {_label(endpoint.path)}")
        lines.append(f"    {entry}->>{handler}: 调用处理器")
        for index, module_name in enumerate(_relevant_dependencies(endpoint, modules)):
            participant = f"M{index}"
            module = modules[module_name]
            lines.append(f"    participant {participant} as {_label(module.name)} · {_label(module.role)}")
            lines.append(f"    {handler}->>{participant}: 模块依赖推断")
            lines.append(f"    {participant}-->>{handler}: 返回")
        lines.append(f"    {handler}-->>{entry}: 返回结果")
        lines.append(f"    {entry}-->>U: HTTP 响应")
        lines.append(f"    Note over U,{entry}: 源码证据 {_label(endpoint.source_path)}:{endpoint.line_number}")
    elif insight.modules:
        ordered = _ordered_modules(insight.modules)[:6]
        previous = "U"
        for index, module in enumerate(ordered):
            participant = f"M{index}"
            lines.append(f"    participant {participant} as {_label(module.name)} · {_label(module.role)}")
            lines.append(f"    {previous}->>{participant}: 模块交互")
            previous = participant
        lines.append("    Note over U,M0: 当前静态分析未识别到可验证接口，展示模块级交互")
    else:
        lines.append("    Note over U: 当前静态分析未识别到可验证交互")
    return "\n".join(lines)


def _representative_endpoint(insight):
    if not insight.endpoints:
        return None
    priorities = ("/repository", "/api", "/v2", "/internal", "/")
    method_priority = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4, "HEAD": 5, "ANY": 6}
    return min(
        insight.endpoints,
        key=lambda item: (
            next((index for index, prefix in enumerate(priorities) if item.path.startswith(prefix)), len(priorities)),
            len(item.path), item.path, method_priority.get(item.method, 9), item.handler,
        ),
    )


def _relevant_dependencies(endpoint, modules: dict) -> list[str]:
    if endpoint.module not in modules:
        return []
    role_priority = {
        "核心": 0, "协议适配": 1, "持久化": 2, "存储": 3,
        "功能模块": 4, "入口服务": 5, "界面": 8, "迁移": 8, "测试": 9,
    }
    context = f"{endpoint.path} {endpoint.handler}".casefold()
    candidates = []
    for name in modules[endpoint.module].dependencies:
        module = modules.get(name)
        if not module or module.role in {"界面", "迁移", "测试"}:
            continue
        if module.role == "协议适配":
            protocol = name.casefold().replace("protocol-", "").replace("protocol_", "")
            if protocol and protocol not in context:
                continue
        candidates.append(module)
    candidates.sort(key=lambda item: (role_priority.get(item.role, 7), item.name))
    return [item.name for item in candidates[:5]]


def _ordered_modules(modules):
    priority = {
        "入口服务": 0, "界面": 1, "协议适配": 2, "核心": 3,
        "持久化": 4, "存储": 5, "迁移": 6, "功能模块": 7, "测试": 8,
    }
    return sorted(modules, key=lambda item: (priority.get(item.role, 9), item.name))


def _node_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return cleaned if cleaned and not cleaned[0].isdigit() else f"node_{cleaned}"


def _participant_id(value: str) -> str:
    return "P_" + _node_id(value)


def _label(value: str) -> str:
    return str(value).replace('"', "'").replace("\n", " ")
