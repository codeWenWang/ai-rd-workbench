from __future__ import annotations

from pathlib import Path

from app.domain.errors import ResourceNotFound, ValidationError


class ProjectUseCase:
    def __init__(self, projects, remote_repositories=None) -> None:
        self.projects = projects
        self.remote_repositories = remote_repositories

    def create(
        self,
        name: str,
        root_path: str = "",
        *,
        source_type: str = "local",
        repository_url: str = "",
    ):
        if source_type == "local":
            root = Path(root_path).expanduser().resolve()
            if not root.is_dir():
                raise ValidationError("项目目录不存在或不可读取")
            return self.projects.create(
                name=name.strip() or root.name,
                root_path=str(root),
                source_type="local",
            )
        if source_type not in {"github", "gitee"}:
            raise ValidationError("不支持的项目来源")
        if not self.remote_repositories:
            raise ValidationError("远程项目功能不可用")
        remote = self.remote_repositories.clone(
            repository_url,
            expected_source=source_type,
        )
        if remote.cache_path is None:
            raise ValidationError("远程项目缓存创建失败")
        return self.projects.create(
            name=name.strip() or remote.name,
            root_path=str(remote.cache_path),
            source_type=remote.source_type,
            source_uri=remote.url,
        )

    def get(self, project_id: str):
        return self.projects.get(project_id)

    def list(self):
        return self.projects.list()

    def update(self, project_id: str, *, name: str):
        project = self.projects.get(project_id)
        if not project:
            raise ResourceNotFound("project not found")
        normalized = name.strip()
        if not normalized:
            raise ValidationError("项目名称不能为空")
        return self.projects.update(project_id, name=normalized)

    def prepare_for_scan(self, project_id: str) -> list[str]:
        project = self.projects.get(project_id)
        if not project:
            raise ResourceNotFound("project not found")
        if project.source_type not in {"github", "gitee"}:
            return []
        if not self.remote_repositories:
            raise ValidationError("远程项目功能不可用")
        return self.remote_repositories.update(project.root_path)

    def delete(self, project_id: str) -> None:
        project = self.projects.get(project_id)
        if not project:
            raise ResourceNotFound("project not found")
        if project.source_type in {"github", "gitee"}:
            if not self.remote_repositories:
                raise ValidationError("远程项目功能不可用")
            self.remote_repositories.remove(project.root_path)
        self.projects.delete(project_id)
