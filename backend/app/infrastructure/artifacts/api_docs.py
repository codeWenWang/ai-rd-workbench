def render_api_docs(project, insight) -> str:
    lines = [
        f"# {project.name} 接口文档", "",
        f"源码版本：`{project.source_revision}`", "",
        f"识别项目类型：{insight.project_type}", "",
    ]
    if not insight.endpoints:
        lines.append("当前静态分析未识别到可验证接口。")
        return "\n".join(lines)
    for endpoint in insight.endpoints:
        lines.extend([
            f"## {endpoint.method} {endpoint.path}", "",
            f"- 框架：{endpoint.framework}",
            f"- 模块：`{endpoint.module}`",
            f"- 处理器：`{endpoint.handler}`",
            f"- 源码：`{endpoint.source_path}:{endpoint.line_number}`",
            "- 参数与响应：静态分析未完全确认", "",
        ])
    return "\n".join(lines)
