import re
from os.path import commonprefix


def render_architecture(insight) -> str:
    if len(insight.modules) > 12:
        return _render_grouped_architecture(insight.modules)
    lines = ["flowchart TB", '    client["客户端 / 调用方"]']
    if not insight.modules:
        lines.append('    project["当前静态分析未识别到可聚合模块"]')
        return "\n".join(lines)
    layers = (
        ("client_layer", "客户端层", {"界面"}),
        ("business_layer", "业务服务层", {"入口服务", "核心", "协议适配", "功能模块", "测试", "迁移"}),
        ("data_layer", "数据层", {"持久化", "存储"}),
    )
    for layer_id, layer_name, roles in layers:
        grouped = [module for module in insight.modules if module.role in roles]
        if not grouped:
            continue
        lines.append(f'    subgraph {layer_id}["{layer_name}"]')
        for module in grouped:
            module_id = _node_id(module.name)
            languages = " / ".join(module.languages[:3]) or "待识别"
            lines.append(
                f'        {module_id}["{_label(module.name)}<br/>{_label(module.role)} · {_label(languages)} · {module.file_count} 文件"]'
            )
        lines.append("    end")
    module_names = {module.name for module in insight.modules}
    for module in insight.modules:
        for dependency in module.dependencies:
            if dependency in module_names:
                lines.append(f"    {_node_id(module.name)} --> {_node_id(dependency)}")
    entry_modules = [module for module in insight.modules if module.role in {"界面", "入口服务"}]
    if not entry_modules:
        entry_modules = insight.modules[:1]
    for module in entry_modules[:4]:
        lines.append(f"    client --> {_node_id(module.name)}")
    lines.extend(_evidence_comments(insight.modules))
    return "\n".join(lines)


def _render_grouped_architecture(modules) -> str:
    layer_ids = {"客户端层": "layer_client", "业务服务层": "layer_business", "数据层": "layer_data"}
    groups = {name: [] for name in layer_ids}
    module_layers = {}
    for module in modules:
        layer = _architecture_layer(module.role)
        groups[layer].append(module)
        module_layers[module.name] = layer
    lines = ["flowchart TB"]
    for layer, grouped in groups.items():
        if not grouped:
            continue
        node_id = layer_ids[layer]
        names = [f"{item.name}（{item.role}）" for item in sorted(grouped, key=lambda item: item.name)]
        shown, remainder = _group_summary(names)
        lines.append(
            f'    {node_id}["{_label(layer)} · {len(names)} 个模块<br/>{_label(shown)}{remainder}"]'
        )
    edges = set()
    for module in modules:
        for dependency in module.dependencies:
            target_layer = module_layers.get(dependency)
            source_layer = module_layers.get(module.name)
            if target_layer and target_layer != source_layer:
                edges.add((source_layer, target_layer))
    for source_layer, target_layer in sorted(edges):
        source_id = layer_ids[source_layer]
        target_id = layer_ids[target_layer]
        lines.append(f"    {source_id} --> {target_id}")
    lines.extend(_evidence_comments(modules))
    return "\n".join(lines)


def _evidence_comments(modules) -> list[str]:
    lines = []
    for module in modules:
        layer = _architecture_layer(module.role)
        module_label = f"{module.name}（{module.role}）"
        for path in module.evidence_paths:
            lines.append(
                f"    %% evidence: {_label(layer)} / {_label(module_label)} / {_label(path)}"
            )
    return lines


def _architecture_layer(role: str) -> str:
    if role == "界面":
        return "客户端层"
    if role in {"持久化", "存储"}:
        return "数据层"
    return "业务服务层"


def _group_summary(names: list[str]) -> tuple[str, str]:
    if len(names) > 4:
        prefix = commonprefix(names)
        if len(prefix) >= 4 and prefix[-1:] in {"-", "_"}:
            return f"{prefix}*", ""
        return " / ".join(names[:3]), f"<br/>另有 {len(names) - 3} 个模块"
    return " / ".join(names), ""


def render_flow(insight) -> str:
    lines = [
        "flowchart TD",
        '    start(["开始"])',
        '    input[/"接收请求"/]',
        '    has_route{"识别到可验证流程？"}',
        "    start --> input --> has_route",
    ]
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
        lines.append(f'    has_route -->|"是"| {entry_id} --> {handler_id}')
        previous = handler_id
        for index, module_name in enumerate(_relevant_dependencies(endpoint, modules)):
            module = modules[module_name]
            node_id = f"step_{index}_{_node_id(module_name)}"
            lines.append(f'    {node_id}["{_label(module.name)} · {_label(module.role)}"]')
            lines.append(f"    {previous} --> {node_id}")
            previous = node_id
        lines.append('    response[/"返回响应"/]')
        lines.append(f"    {previous} --> response")
        lines.append("    response --> finish")
    elif insight.modules:
        ordered = _ordered_modules(insight.modules)
        previous = "has_route"
        for index, module in enumerate(ordered[:8]):
            node_id = f"module_{index}_{_node_id(module.name)}"
            lines.append(f'    {node_id}["{_label(module.name)} · {_label(module.role)}"]')
            condition = ' -->|"是"| ' if previous == "has_route" else " --> "
            lines.append(f"    {previous}{condition}{node_id}")
            previous = node_id
        lines.append(f'    {previous} --> output[/"输出模块主链路"/] --> finish')
    else:
        lines.append('    has_route -->|"是"| empty["展示已识别流程"] --> finish')
    lines.extend([
        '    has_route -->|"否"| unavailable["说明分析不足"] --> finish',
        '    finish(["结束"])',
    ])
    return "\n".join(lines)


def render_sequence(insight) -> str:
    endpoint = _representative_endpoint(insight)
    modules = {module.name: module for module in insight.modules}
    lines = ["sequenceDiagram", "    actor U as 外部用户"]
    if endpoint:
        gateway = "G"
        business = "B"
        entry_name = _label(endpoint.module or "应用")
        handler_name = _label((endpoint.handler or "业务处理器").rsplit(".", 1)[0] or "业务处理器")
        dependencies = [modules[name] for name in _sequence_dependencies(endpoint, modules)]
        lines.extend([
            f"    participant {gateway} as 前端 / 网关【{entry_name}】",
            f"    participant {business} as 业务服务【{handler_name}】",
        ])
        dependency_ids = []
        for index, module in enumerate(dependencies):
            kind = _sequence_kind(module)
            prefix = {"middleware": "M", "database": "D", "business": "S"}[kind]
            participant = f"{prefix}{index}"
            dependency_ids.append((participant, module, kind))
            lines.append(f"    participant {participant} as {_sequence_participant_label(module)}")
        parameter_text = _sequence_parameters(endpoint.path)
        lines.extend([
            f"    U->>{gateway}: {_label(endpoint.method)} {_label(endpoint.path)}({parameter_text}) : 发起请求",
            f"    activate {gateway}",
            f"    {gateway}->>{business}: {_label(endpoint.handler)}({parameter_text}) : 处理请求",
            f"    activate {business}",
            "    alt 正常流程",
        ])
        for participant, module, kind in dependency_ids:
            module_name = _label(module.name)
            if kind == "middleware":
                lines.append(f"        {business}-){participant}: {module_name}(状态) : 发布异步消息")
                continue
            action = "查询数据" if kind == "database" else "调用模块"
            lines.extend([
                f"        {business}->>{participant}: {module_name}(关键参数) : {action}",
                f"        activate {participant}",
                f"        {participant}-->>{business}: {module_name}(结果) : 返回数据",
                f"        deactivate {participant}",
            ])
        lines.extend([
            f"        {business}-->>{gateway}: 业务结果(状态) : 处理成功",
            f"        {gateway}-->>U: HTTP 响应(状态) : 返回成功",
            "    else 关键异常",
            f"        {business}-->>{gateway}: 错误(状态) : 校验或业务失败",
            f"        {gateway}-->>U: HTTP 响应(状态) : 返回错误",
            "    end",
            f"    deactivate {business}",
            f"    deactivate {gateway}",
            f"    %% evidence: 业务服务层 / {_label(endpoint.module or '应用')}（入口服务） / {_label(endpoint.source_path)}:{endpoint.line_number}",
        ])
        for _, module, _ in dependency_ids:
            layer = _architecture_layer(module.role)
            for path in module.evidence_paths:
                lines.append(f"    %% evidence: {_label(layer)} / {_label(module.name)}（{_label(module.role)}） / {_label(path)}")
        return "\n".join(lines)

    if insight.modules:
        ordered = sorted(insight.modules, key=lambda item: (_sequence_kind_priority(item), item.name))[:5]
        lines.extend([f"    participant S{index} as {_sequence_participant_label(module)}" for index, module in enumerate(ordered)])
        lines.extend([
            "    U->>S0: 项目入口(无) : 发起请求",
            "    activate S0",
            "    alt 正常流程",
            "        S0-->>U: 处理结果(状态) : 返回成功",
            "    else 关键异常",
            "        S0-->>U: 错误(状态) : 无法确认处理结果",
            "    end",
            "    deactivate S0",
        ])
    else:
        lines.extend([
            '    participant S0 as 业务服务【未识别模块】',
            '    U->>S0: 项目入口(无) : 发起请求',
            '    S0-->>U: 处理结果(状态) : 无法确认处理结果',
        ])
    return "\n".join(lines)


def _sequence_parameters(path: str) -> str:
    parameters = re.findall(r"\{([^}]+)\}", str(path or ""))
    return ",".join(parameters) or "无"


def _sequence_kind(module) -> str:
    text = f"{module.name} {module.role}".casefold()
    if re.search(r"database|mysql|postgres|jdbc|storage|repository|dao|持久化|存储|数据库", text):
        return "database"
    if re.search(r"mq|message|queue|kafka|rabbit|event|notify|notification|redis|cache|消息|队列|缓存|中间件", text):
        return "middleware"
    return "business"


def _sequence_kind_priority(module) -> int:
    return {"business": 0, "middleware": 1, "database": 2}[_sequence_kind(module)]


def _sequence_participant_label(module) -> str:
    kind = _sequence_kind(module)
    label = {"business": "业务服务", "middleware": "中间件", "database": "数据库"}[kind]
    return f"{label}【{_label(module.name)}】"


def _sequence_dependencies(endpoint, modules: dict) -> list[str]:
    if endpoint.module not in modules:
        return []
    candidates = []
    context = f"{endpoint.path} {endpoint.handler}".casefold()
    for name in modules[endpoint.module].dependencies:
        module = modules.get(name)
        if not module or module.role in {"界面", "迁移", "测试"}:
            continue
        if module.role == "协议适配":
            protocol = name.casefold().replace("protocol-", "").replace("protocol_", "")
            if protocol and protocol not in context:
                continue
        candidates.append(module)
    candidates.sort(key=lambda item: (_sequence_kind_priority(item), item.name))
    return [item.name for item in candidates[:5]]


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
    return sorted(modules, key=lambda item: (_role_priority(item.role), item.name))


def _role_priority(role: str) -> int:
    return {
        "入口服务": 0, "界面": 1, "协议适配": 2, "核心": 3,
        "持久化": 4, "存储": 5, "迁移": 6, "功能模块": 7, "测试": 8,
    }.get(role, 9)


def _node_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return cleaned if cleaned and not cleaned[0].isdigit() else f"node_{cleaned}"


def _participant_id(value: str) -> str:
    return "P_" + _node_id(value)


def _label(value: str) -> str:
    return str(value).replace('"', "'").replace("\n", " ")
