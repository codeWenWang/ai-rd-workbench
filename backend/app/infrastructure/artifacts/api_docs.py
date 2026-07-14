def render_api_docs(project, files, routes) -> str:
    file_paths = {item.id: item.relative_path for item in files}
    lines = [f"# {project.name} 接口文档", "", f"源码版本：`{project.source_revision}`", ""]
    if not routes:
        lines.append("静态分析未识别到 FastAPI 路由。")
        return "\n".join(lines)
    for route in routes:
        location = file_paths.get(route.project_file_id, "unknown")
        lines.extend([
            f"## {route.method} {route.path}",
            "",
            f"- 处理器：`{route.handler}`",
            f"- 源码：`{location}:{route.line_number}`",
            "- 参数：静态分析未确认",
            "- 响应：静态分析未确认",
            "",
        ])
    return "\n".join(lines)
