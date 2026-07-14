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
        parsed_items = [
            (item, self.parsers.parse(item.relative_path, item.content))
            for item in scan.files
        ]
        self.analysis.replace_scan(project_id, parsed_items)
        tech_stack = sorted({item.language for item in scan.files})
        self.projects.update_scan(
            project_id,
            revision=scan.revision,
            tech_stack=tech_stack,
        )
        symbol_count = sum(len(parsed.symbols) for _, parsed in parsed_items)
        route_count = sum(len(parsed.routes) for _, parsed in parsed_items)
        relation_count = sum(
            len(parsed.imports) + len(parsed.calls) for _, parsed in parsed_items
        )
        return ProjectScanSummary(
            project_id=project_id,
            revision=scan.revision,
            file_count=len(scan.files),
            symbol_count=symbol_count,
            route_count=route_count,
            relation_count=relation_count,
            skipped_count=len(scan.skipped),
        )
