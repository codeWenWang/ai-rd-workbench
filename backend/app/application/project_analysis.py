from app.domain.entities import ProjectScanSummary
from app.domain.errors import ResourceNotFound


class ProjectAnalysisUseCase:
    def __init__(self, projects, analysis, scanner, parsers) -> None:
        self.projects = projects
        self.analysis = analysis
        self.scanner = scanner
        self.parsers = parsers

    def scan(self, project_id: str) -> ProjectScanSummary:
        project = self.projects.get(project_id)
        if not project:
            raise ResourceNotFound("project not found")
        scan = self.scanner.scan(project.root_path)
        return self._apply_scan(project, scan)

    def scan_incremental(self, project_id: str) -> ProjectScanSummary:
        """Refresh source facts for review without semantic/vector indexing.

        The regular project scan also performs embedding/index work at the API
        layer. Reviews only need current file hashes and parsed structure, so
        this path reuses the stored snapshot when the revision is unchanged and
        avoids the expensive indexing stage entirely.
        """
        project = self.projects.get(project_id)
        if not project:
            raise ResourceNotFound("project not found")
        scan = self.scanner.scan(project.root_path)
        if project.source_revision == scan.revision:
            files = self.analysis.list_files(project_id)
            return ProjectScanSummary(
                project_id=project_id,
                revision=scan.revision,
                file_count=len(files),
                symbol_count=len(self.analysis.list_symbols(project_id)),
                route_count=len(self.analysis.list_routes(project_id)),
                relation_count=len(self.analysis.list_relations(project_id)),
                skipped_count=len(scan.skipped),
            )
        return self._apply_scan(project, scan)

    def _apply_scan(self, project, scan) -> ProjectScanSummary:
        if project.source_revision and project.source_revision != scan.revision:
            self.analysis.mark_artifacts_stale(project.id)
        parsed_items = [
            (item, self.parsers.parse(item.relative_path, item.content))
            for item in scan.files
        ]
        server_routes = {
            (route.method, route.path)
            for _, parsed in parsed_items
            for route in parsed.routes
            if not route.handler.startswith("前端 ")
        }
        for _, parsed in parsed_items:
            parsed.routes = [
                route for route in parsed.routes
                if not (
                    route.handler.startswith("前端 ")
                    and (route.method, route.path) in server_routes
                )
            ]
        self.analysis.replace_scan(project.id, parsed_items)
        tech_stack = _main_tech_stack(scan.files)
        self.projects.update_scan(
            project.id,
            revision=scan.revision,
            tech_stack=tech_stack,
        )
        symbol_count = sum(len(parsed.symbols) for _, parsed in parsed_items)
        route_count = sum(len(parsed.routes) for _, parsed in parsed_items)
        relation_count = sum(
            len(parsed.imports) + len(parsed.calls) for _, parsed in parsed_items
        )
        return ProjectScanSummary(
            project_id=project.id,
            revision=scan.revision,
            file_count=len(scan.files),
            symbol_count=symbol_count,
            route_count=route_count,
            relation_count=relation_count,
            skipped_count=len(scan.skipped),
        )


def _main_tech_stack(files) -> list[str]:
    languages = {item.language.casefold() for item in files}
    content = "\n".join(item.content[:20000] for item in files)
    stack = []
    for language in ("java", "python", "typescript", "javascript", "html", "css"):
        if language in languages:
            stack.append(language)
    framework_markers = (
        ("Spring Boot", ("@SpringBootApplication", "spring-boot")),
        ("FastAPI", ("FastAPI(", "from fastapi", "import fastapi")),
        ("LangChain", ("langchain",)),
        ("LangGraph", ("langgraph",)),
        ("Vue", ("vue", "createApp(")),
        ("React", ("from 'react'", 'from "react"', "react-dom")),
    )
    lowered = content.casefold()
    for label, markers in framework_markers:
        if any(marker.casefold() in lowered for marker in markers):
            stack.append(label)
    return list(dict.fromkeys(stack))
