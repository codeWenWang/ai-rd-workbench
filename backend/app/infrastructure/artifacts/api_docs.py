from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import quote


ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
UNKNOWN = object()


@dataclass(slots=True)
class ApiParameter:
    name: str
    type_name: str
    location: str
    required: bool = True


@dataclass(slots=True)
class JavaField:
    name: str
    type_name: str


@dataclass(slots=True)
class JavaModel:
    name: str
    type_parameters: list[str] = field(default_factory=list)
    fields: list[JavaField] = field(default_factory=list)


@dataclass(slots=True)
class ApiEndpointDoc:
    title: str
    method: str
    path: str
    parameters: list[ApiParameter]
    path_example: str
    request_body: object = UNKNOWN
    response_body: object = UNKNOWN
    source_path: str = ""
    line_number: int = 0
    notes: list[str] = field(default_factory=list)


def render_api_docs(project, insight, files=None) -> str:
    files = list(files or [])
    file_by_path = {item.relative_path: item for item in files}
    models = _java_models(files)
    documents = []
    for endpoint in sorted(
        insight.endpoints,
        key=lambda item: (item.source_path, item.line_number, item.method, item.path),
    ):
        if endpoint.method not in ALLOWED_METHODS:
            continue
        source = file_by_path.get(endpoint.source_path)
        if source and source.language == "java" and not _is_rest_endpoint(source.content, endpoint):
            continue
        documents.append(_endpoint_document(endpoint, source, models))

    lines = [
        f"# {project.name} 接口文档", "",
        f"源码版本：`{project.source_revision}`", "",
        f"识别项目类型：{insight.project_type}", "",
        "## 1. 接口说明", "",
    ]
    if not documents:
        lines.append("当前静态分析未识别到 GET、POST、PUT、PATCH、DELETE 接口。")
        return "\n".join(lines)

    for index, document in enumerate(documents, start=1):
        lines.extend(_render_endpoint(document, index))
    return "\n".join(lines)


def _endpoint_document(endpoint, source, models: dict[str, JavaModel]) -> ApiEndpointDoc:
    if not source or source.language != "java":
        parameters = [
            ApiParameter(name, "string", "路径参数")
            for name in re.findall(r"\{([^}]+)\}", endpoint.path)
        ]
        request_body = (
            {"field": "string"}
            if endpoint.method in {"POST", "PUT", "PATCH"} else UNKNOWN
        )
        return ApiEndpointDoc(
            title=_fallback_title(endpoint.handler, endpoint.method, endpoint.path),
            method=endpoint.method,
            path=endpoint.path,
            parameters=parameters,
            path_example=_path_example(endpoint.path, parameters),
            request_body=request_body,
            response_body={"code": 0, "message": "string", "data": {}},
            source_path=endpoint.source_path,
            line_number=endpoint.line_number,
            notes=["请求体与响应为通用静态推断样例，请以实际接口实现和运行结果为准"],
        )

    method_name = endpoint.handler.rsplit(".", 1)[-1]
    signature = _java_method_signature(source.content, method_name, endpoint.line_number)
    if not signature:
        return ApiEndpointDoc(
            title=_fallback_title(endpoint.handler, endpoint.method, endpoint.path),
            method=endpoint.method,
            path=endpoint.path,
            parameters=[],
            path_example=_path_example(endpoint.path, []),
            source_path=endpoint.source_path,
            line_number=endpoint.line_number,
            notes=["静态分析未找到完整方法签名"],
        )

    return_type, parameter_text, context = signature
    parameters = _java_parameters(parameter_text, endpoint.path)
    body_parameter = next((item for item in parameters if item.location == "请求体"), None)
    request_body = (
        _sample_for_type(body_parameter.type_name, models, field_name=body_parameter.name, schema=True)
        if body_parameter else UNKNOWN
    )
    response_body = _sample_for_type(return_type, models, schema=True)
    notes = []
    if request_body is UNKNOWN and body_parameter:
        notes.append(f"未找到请求体类型 {body_parameter.type_name} 的字段定义")
    if response_body is UNKNOWN:
        notes.append(f"未确认返回类型 {return_type} 的具体响应结构")
    return ApiEndpointDoc(
        title=_endpoint_title(context, endpoint.handler, endpoint.method, endpoint.path),
        method=endpoint.method,
        path=endpoint.path,
        parameters=parameters,
        path_example=_path_example(endpoint.path, parameters),
        request_body=request_body,
        response_body=response_body,
        source_path=endpoint.source_path,
        line_number=endpoint.line_number,
        notes=notes,
    )


def _render_endpoint(document: ApiEndpointDoc, index: int) -> list[str]:
    parameters = [item for item in document.parameters if item.location != "请求体"]
    body = next((item for item in document.parameters if item.location == "请求体"), None)
    if not parameters and not body:
        parameter_text = "无"
    else:
        parts = [
            f"{item.name}（{item.location}，{item.type_name}{'，必填' if item.required else '，可选'}）"
            for item in parameters
        ]
        if body:
            parts.append(f"{body.name}（请求体，{body.type_name}）")
        parameter_text = "；".join(parts)

    lines = [
        f"### 1.{index} {document.title}", "",
        f"**请求路径：** `{document.path}`", "",
        f"**请求方式：** `{document.method}`", "",
        f"**请求参数：** {parameter_text}", "",
    ]
    if document.request_body is not UNKNOWN:
        lines.extend([
            f"**请求地址样例：** `{document.path_example}`", "",
            "**请求样例：**", "", "```json",
            _json(document.request_body), "```", "",
        ])
    else:
        lines.extend([f"**请求样例：** `{document.path_example}`", ""])

    lines.extend(["**响应数据格式：**", ""])
    if document.response_body is UNKNOWN:
        lines.extend(["静态分析未确认具体响应结构。", ""])
    else:
        lines.extend(["```json", _json(document.response_body), "```", ""])
    source_location = quote(document.source_path, safe="/-._~")
    lines.extend([
        f"**源码：** [查看接口关键源码](source://{source_location}:{document.line_number})", "",
    ])
    return lines


def _is_rest_endpoint(content: str, endpoint) -> bool:
    class_name = endpoint.handler.split(".", 1)[0]
    class_match = re.search(rf"\bclass\s+{re.escape(class_name)}\b", content)
    class_header = content[:class_match.start()] if class_match else content
    if "@RestController" in class_header[-2000:]:
        return True
    lines = content.splitlines()
    start = max(0, endpoint.line_number - 8)
    end = min(len(lines), endpoint.line_number + 8)
    return "@ResponseBody" in "\n".join(lines[start:end])


def _java_method_signature(content: str, method_name: str, line_number: int):
    pattern = re.compile(
        r"^[ \t]*(?P<annotations>(?:@[A-Za-z_$][\w$.]*(?:\s*\([^)]*\))?[ \t]*\n[ \t]*)*)"
        r"(?:public|protected|private)\s+"
        r"(?:static\s+|final\s+|synchronized\s+|default\s+)*"
        r"(?:<[^>]+>\s*)?"
        r"(?P<return>[A-Za-z_$][\w$., ?<>\[\]]*)\s+"
        rf"{re.escape(method_name)}\s*\((?P<params>.*?)\)\s*"
        r"(?:throws\s+[^\{]+)?\{",
        re.S | re.M,
    )
    candidates = []
    for match in pattern.finditer(content):
        match_line = content.count("\n", 0, match.start()) + 1
        candidates.append((abs(match_line - line_number), match))
    if not candidates:
        return None
    match = min(candidates, key=lambda item: item[0])[1]
    context_start = max(0, match.start() - 1200)
    context = content[context_start:match.start()] + match.group("annotations")
    return match.group("return").strip(), match.group("params").strip(), context


def _java_parameters(text: str, path: str) -> list[ApiParameter]:
    parameters = []
    for raw in _split_top_level(text):
        if not raw.strip():
            continue
        annotations = {
            name.rsplit(".", 1)[-1]: args or ""
            for name, args in re.findall(
                r"@([A-Za-z_$][\w$.]*)(?:\s*\(([^)]*)\))?", raw
            )
        }
        declaration = re.sub(
            r"@[A-Za-z_$][\w$.]*(?:\s*\([^)]*\))?", "", raw
        )
        declaration = re.sub(r"\bfinal\b", "", declaration).strip()
        parts = declaration.split()
        if len(parts) < 2:
            continue
        name = parts[-1].replace("...", "")
        type_name = " ".join(parts[:-1]).replace("...", "[]").strip()
        simple_type = _generic_type(type_name)[0].rsplit(".", 1)[-1]
        if simple_type in {
            "HttpServletRequest", "HttpServletResponse", "Principal",
            "Authentication", "BindingResult", "Pageable",
        }:
            continue
        if "PathVariable" in annotations:
            location = "路径参数"
            external_name = _annotation_name(annotations["PathVariable"]) or name
        elif "RequestParam" in annotations:
            location = "查询参数"
            external_name = _annotation_name(annotations["RequestParam"]) or name
        elif "RequestBody" in annotations:
            location = "请求体"
            external_name = name
        elif "RequestHeader" in annotations:
            location = "请求头"
            external_name = _annotation_name(annotations["RequestHeader"]) or name
        elif "RequestPart" in annotations:
            location = "文件参数"
            external_name = _annotation_name(annotations["RequestPart"]) or name
        elif f"{{{name}}}" in path:
            location = "路径参数"
            external_name = name
        else:
            location = "方法参数"
            external_name = name
        required = not any("required" in args and "false" in args.casefold() for args in annotations.values())
        parameters.append(ApiParameter(external_name, type_name, location, required))
    return parameters


def _annotation_name(args: str) -> str:
    match = re.search(r"(?:value|name)\s*=\s*['\"]([^'\"]+)['\"]", args)
    if not match:
        match = re.search(r"^\s*['\"]([^'\"]+)['\"]", args)
    return match.group(1) if match else ""


def _path_example(path: str, parameters: list[ApiParameter]) -> str:
    result = path
    for parameter in parameters:
        if parameter.location == "路径参数":
            result = result.replace(f"{{{parameter.name}}}", str(_scalar_sample(parameter.type_name, parameter.name)))
    result = re.sub(r"\{[^}]+\}", "1", result)
    query = [
        f"{item.name}={_scalar_sample(item.type_name, item.name)}"
        for item in parameters if item.location == "查询参数"
    ]
    return result + (("?" + "&".join(query)) if query else "")


def _endpoint_title(context: str, handler: str, method: str, path: str) -> str:
    semantic = _rest_semantic_title(method, path)
    if semantic:
        return semantic
    operation = re.search(r"@Operation\s*\([^)]*summary\s*=\s*['\"]([^'\"]+)['\"]", context, re.S)
    if operation:
        return operation.group(1).strip()
    api_operation = re.search(r"@ApiOperation\s*\(\s*(?:value\s*=\s*)?['\"]([^'\"]+)['\"]", context, re.S)
    if api_operation:
        return api_operation.group(1).strip()
    comments = re.findall(r"/\*\*(.*?)\*/", context, re.S)
    if comments:
        cleaned = [
            re.sub(r"^\s*\*\s?", "", line).strip()
            for line in comments[-1].splitlines()
        ]
        summary = " ".join(line for line in cleaned if line and not line.startswith("@"))
        if summary:
            return summary
    return _fallback_title(handler, method, path)


def _fallback_title(handler: str, method: str, path: str) -> str:
    semantic = _rest_semantic_title(method, path)
    if semantic:
        return semantic
    name = handler.rsplit(".", 1)[-1]
    normalized_name = name.casefold()
    resource = _path_resource(path)
    if normalized_name in {"list", "findall", "getall", "page"}:
        return f"{resource} 列表查询"
    if normalized_name in {"get", "find", "findbyid", "getbyid", "read"}:
        prefix = "根据 ID 查询" if re.search(r"\{[^}]*id[^}]*\}", path, re.I) else "查询"
        return f"{prefix} {resource}"
    if normalized_name in {"create", "add", "save", "insert", "post"}:
        return f"新增 {resource}"
    if normalized_name in {"update", "modify", "edit", "put"}:
        return f"修改 {resource}"
    if normalized_name in {"delete", "remove", "deletebyid"}:
        return f"删除 {resource}"
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").strip()
    if method == "GET":
        return f"{words} 查询" if words else "查询"
    return f"{words} 操作" if words else f"{method} 操作"


_RESOURCE_LABELS = {
    "user": "用户",
    "users": "用户",
    "category": "分类",
    "categories": "分类",
    "dish": "菜品",
    "dishes": "菜品",
    "setmeal": "套餐",
    "setmeals": "套餐",
    "employee": "员工",
    "employees": "员工",
    "order": "订单",
    "orders": "订单",
    "customer": "客户",
    "customers": "客户",
    "address": "地址",
    "addresses": "地址",
}
_ACTION_LABELS = {
    "pay": "支付",
    "payment": "支付",
    "cancel": "取消",
    "confirm": "确认",
    "submit": "提交",
    "login": "登录",
    "logout": "退出登录",
    "check": "校验",
}


def _rest_semantic_title(method: str, path: str) -> str:
    """Use HTTP resource shape for stable, human-readable endpoint names."""
    method = method.upper()
    segments = [item for item in path.strip("/").split("/") if item and item not in {"*", "**"}]
    values = [item for item in segments if not item.startswith("{")]
    if not values:
        return ""
    last = values[-1].casefold()
    if last in {"item", "items", "detail", "details"} and len(values) >= 2:
        parent = _RESOURCE_LABELS.get(values[-2].casefold())
        if parent:
            return f"查询{parent}下商品明细"
    action = _ACTION_LABELS.get(last)
    if action and len(values) >= 2:
        resource = _RESOURCE_LABELS.get(values[-2].casefold())
        if resource:
            return f"{resource}{action}（动作型资源）"
    resource_key = next(
        (item.casefold() for item in reversed(values) if item.casefold() in _RESOURCE_LABELS),
        "",
    )
    resource = _RESOURCE_LABELS.get(resource_key)
    if not resource:
        return ""
    has_path_parameter = any(item.startswith("{") for item in segments)
    if method == "GET":
        return f"查询单个{resource}" if has_path_parameter else f"查询{resource}列表"
    if method == "POST":
        return f"创建{resource}"
    if method == "PUT":
        return f"修改{resource}（全量）"
    if method == "PATCH":
        return f"局部修改{resource}"
    if method == "DELETE":
        return f"删除{resource}"
    return ""


def _path_resource(path: str) -> str:
    ignored = {"api", "internal", "service", "rest", "v1", "v2", "v3", "current"}
    segments = [
        item for item in path.strip("/").split("/")
        if item and item not in {"**", "*"} and not item.startswith("{")
    ]
    candidates = [item for item in segments if item.casefold() not in ignored]
    value = candidates[-1] if candidates else (segments[-1] if segments else "接口")
    return value.replace("-", " ").replace("_", " ")


def _java_models(files) -> dict[str, JavaModel]:
    models = {}
    class_pattern = re.compile(
        r"\bclass\s+(?P<name>[A-Za-z_$][\w$]*)"
        r"(?:\s*<(?P<types>[^>]+)>)?"
    )
    record_pattern = re.compile(
        r"\brecord\s+(?P<name>[A-Za-z_$][\w$]*)"
        r"(?:\s*<(?P<types>[^>]+)>)?\s*"
        r"\((?P<components>.*?)\)\s*(?:implements\s+[^\{]+)?\{",
        re.S,
    )
    field_pattern = re.compile(
        r"\b(?:private|protected|public)\s+"
        r"(?!static\s+)"
        r"(?:final\s+)?(?P<type>[A-Za-z_$][\w$., ?<>\[\]]*)\s+"
        r"(?P<name>[A-Za-z_$][\w$]*)\s*(?:=[^;]*)?;"
    )
    for file in files:
        if file.language != "java":
            continue
        type_starts = sorted(
            [(match.start(), "class", match) for match in class_pattern.finditer(file.content)]
            + [(match.start(), "record", match) for match in record_pattern.finditer(file.content)],
            key=lambda item: item[0],
        )
        for index, (start, kind, match) in enumerate(type_starts):
            model = JavaModel(
                match.group("name"),
                [item.strip() for item in (match.group("types") or "").split(",") if item.strip()],
            )
            if kind == "record":
                fields = []
                for component in _split_top_level(match.group("components")):
                    declaration = re.sub(
                        r"@[A-Za-z_$][\w$.]*(?:\s*\([^)]*\))?", "", component
                    ).strip()
                    parts = declaration.split()
                    if len(parts) >= 2:
                        fields.append(JavaField(parts[-1], " ".join(parts[:-1])))
                model.fields = fields
            else:
                end = type_starts[index + 1][0] if index + 1 < len(type_starts) else len(file.content)
                body = file.content[match.end():end]
                model.fields = [
                    JavaField(field_match.group("name"), field_match.group("type").strip())
                    for field_match in field_pattern.finditer(body)
                ]
            models[model.name] = model
    return models


def _sample_for_type(
    type_name: str,
    models: dict[str, JavaModel],
    *,
    field_name: str = "",
    type_bindings=None,
    depth: int = 0,
    schema: bool = False,
):
    if depth > 5:
        return UNKNOWN
    type_bindings = dict(type_bindings or {})
    normalized = re.sub(r"@[A-Za-z_$][\w$.]*", "", type_name).strip()
    if normalized in type_bindings:
        normalized = type_bindings[normalized]
    base, arguments = _generic_type(normalized)
    simple = base.rsplit(".", 1)[-1]
    if simple in {"void", "Void"}:
        return None
    if simple in {"List", "Collection", "Set", "Iterable", "Page"}:
        if not arguments:
            return []
        item = _sample_for_type(
            arguments[0], models, type_bindings=type_bindings,
            depth=depth + 1, schema=schema,
        )
        return [] if item is UNKNOWN else [item]
    if simple in {"Optional", "ResponseEntity", "HttpEntity"} and arguments:
        return _sample_for_type(
            arguments[0], models, type_bindings=type_bindings,
            depth=depth + 1, schema=schema,
        )
    if simple in {"Map", "HashMap", "LinkedHashMap"}:
        return {}
    scalar = _scalar_sample(simple, field_name, unknown=UNKNOWN, schema=schema)
    if scalar is not UNKNOWN:
        return scalar
    model = models.get(simple)
    if not model:
        return UNKNOWN
    bindings = dict(type_bindings)
    for parameter, argument in zip(model.type_parameters, arguments, strict=False):
        bindings[parameter] = argument
    output = {}
    for item in model.fields:
        value = _sample_for_type(
            item.type_name,
            models,
            field_name=item.name,
            type_bindings=bindings,
            depth=depth + 1,
            schema=schema,
        )
        output[item.name] = None if value is UNKNOWN else value
    return output


def _scalar_sample(type_name: str, field_name: str = "", *, unknown=1, schema: bool = False):
    simple = type_name.rsplit(".", 1)[-1].strip()
    lower_name = field_name.casefold()
    if simple in {"byte", "short", "int", "Integer", "long", "Long", "BigInteger"}:
        return 0 if schema else 1
    if simple in {"float", "Float", "double", "Double", "BigDecimal"}:
        return 0.0 if schema else 1.0
    if simple in {"boolean", "Boolean"}:
        return False if schema else True
    if simple in {"LocalDateTime", "OffsetDateTime", "ZonedDateTime", "Date", "Timestamp"}:
        return "string" if schema else "2026-01-01T00:00:00"
    if simple == "LocalDate":
        return "string" if schema else "2026-01-01"
    if simple in {"String", "char", "Character", "UUID"}:
        if schema:
            return "string"
        if lower_name == "msg" or "message" in lower_name:
            return "success"
        if lower_name == "name" or lower_name.endswith("name"):
            return "张三"
        if lower_name == "code":
            return "success"
        samples = {
            "objectkey": "demo-bucket/tasks/1",
            "endpoint": "https://oss-cn-hangzhou.aliyuncs.com",
            "region": "cn-hangzhou",
            "bucket": "demo-bucket",
            "path": "/tasks/1",
            "resolvedpath": "/data/tasks/1",
            "state": "READY",
            "status": "ACTIVE",
            "email": "zhangsan@example.com",
            "phone": "13800138000",
            "address": "北京市海淀区中关村大街 1 号",
            "title": "研发任务示例",
            "description": "完成项目接口联调",
        }
        return samples.get(lower_name, "示例值")
    return unknown


def _generic_type(type_name: str) -> tuple[str, list[str]]:
    value = type_name.strip()
    if "<" not in value or not value.endswith(">"):
        return value, []
    start = value.find("<")
    return value[:start].strip(), _split_top_level(value[start + 1:-1])


def _split_top_level(value: str) -> list[str]:
    parts = []
    start = 0
    depth = 0
    pairs = {"<": ">", "(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())
    quote = ""
    for index, character in enumerate(value):
        if quote:
            if character == quote and (index == 0 or value[index - 1] != "\\"):
                quote = ""
            continue
        if character in {'"', "'"}:
            quote = character
        elif character in pairs:
            depth += 1
        elif character in closing:
            depth = max(0, depth - 1)
        elif character == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
