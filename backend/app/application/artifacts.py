from app.domain.errors import ResourceNotFound, ValidationError
from app.infrastructure.artifacts import (
    render_api_docs,
    render_architecture,
    render_flow,
    render_sequence,
)


class ArtifactUseCase:
    FORMATS = {
        "architecture": "mermaid",
        "flow": "mermaid",
        "sequence": "mermaid",
        "api_docs": "markdown",
    }

    def __init__(self, projects, analysis) -> None:
        self.projects = projects
        self.analysis = analysis

    def generate(self, project_id: str, artifact_type: str):
        if artifact_type not in self.FORMATS:
            raise ValidationError("unsupported artifact type")
        project = self.projects.get(project_id)
        if not project:
            raise ResourceNotFound("project not found")
        if not project.source_revision:
            raise ValidationError("请先扫描项目")
        files = self.analysis.list_files(project_id)
        routes = self.analysis.list_routes(project_id)
        relations = self.analysis.list_relations(project_id)
        if artifact_type == "architecture":
            content = render_architecture(files, relations)
        elif artifact_type == "flow":
            content = render_flow(files, routes, relations)
        elif artifact_type == "sequence":
            content = render_sequence(files, routes, relations)
        else:
            content = render_api_docs(project, files, routes)
        return self.analysis.save_artifact(
            project_id=project_id,
            artifact_type=artifact_type,
            format=self.FORMATS[artifact_type],
            content=content,
            source_revision=project.source_revision,
        )

    def list(self, project_id: str):
        return self.analysis.list_artifacts(project_id)

    def get(self, artifact_id: str):
        artifact = self.analysis.get_artifact(artifact_id)
        if not artifact:
            raise ResourceNotFound("artifact not found")
        return artifact
