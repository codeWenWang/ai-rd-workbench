from pathlib import Path

from app.domain.errors import ValidationError


class ProjectUseCase:
    def __init__(self, projects) -> None:
        self.projects = projects

    def create(self, name: str, root_path: str):
        root = Path(root_path).expanduser().resolve()
        if not root.is_dir():
            raise ValidationError("项目目录不存在或不可读取")
        return self.projects.create(
            name=name.strip() or root.name,
            root_path=str(root),
            source_type="local",
        )

    def get(self, project_id: str):
        return self.projects.get(project_id)

    def list(self):
        return self.projects.list()

    def delete(self, project_id: str) -> None:
        self.projects.delete(project_id)
