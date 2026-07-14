from pathlib import Path

from app.domain.errors import ValidationError


class LocalDirectorySource:
    def __init__(self, root_path: str | Path) -> None:
        self.root = Path(root_path).expanduser().resolve()
        if not self.root.is_dir():
            raise ValidationError("项目目录不存在或不可读取")

    def resolve_file(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValidationError("项目文件路径越界或不存在")
        return path

    def read_text(self, relative_path: str) -> str:
        return self.resolve_file(relative_path).read_text(encoding="utf-8", errors="replace")
