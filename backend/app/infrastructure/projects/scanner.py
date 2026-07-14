from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from app.infrastructure.projects.source import LocalDirectorySource


IGNORED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".idea", ".cursor", ".venv", "venv",
    "node_modules", "dist", "build", "target", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "coverage", "htmlcov",
}
IGNORED_FILE_PREFIXES = (".env",)
IGNORED_FILE_NAMES = {
    "id_rsa", "id_ed25519", "credentials.json", "secrets.json",
}
LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".md": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
}


@dataclass(slots=True)
class ScannedFile:
    relative_path: str
    language: str
    size_bytes: int
    modified_ns: int
    content_hash: str
    content: str


@dataclass(slots=True)
class ScanResult:
    root_path: str
    revision: str
    files: list[ScannedFile] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


class LocalProjectScanner:
    def __init__(self, *, max_file_bytes: int = 1024 * 1024) -> None:
        self.max_file_bytes = max_file_bytes

    def scan(self, root_path: str | Path) -> ScanResult:
        source = LocalDirectorySource(root_path)
        files: list[ScannedFile] = []
        skipped: list[str] = []
        for path in sorted(source.root.rglob("*"), key=lambda item: item.as_posix().casefold()):
            relative = path.relative_to(source.root)
            if any(part in IGNORED_DIRECTORIES for part in relative.parts):
                continue
            if path.is_symlink() or not path.is_file():
                continue
            name = path.name.casefold()
            language = LANGUAGES.get(path.suffix.casefold())
            if (
                language is None
                or name.startswith(IGNORED_FILE_PREFIXES)
                or name in IGNORED_FILE_NAMES
            ):
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(source.root):
                skipped.append(relative.as_posix())
                continue
            stat = resolved.stat()
            if stat.st_size > self.max_file_bytes:
                skipped.append(relative.as_posix())
                continue
            raw = resolved.read_bytes()
            if b"\x00" in raw[:4096]:
                skipped.append(relative.as_posix())
                continue
            content_hash = sha256(raw).hexdigest()
            files.append(ScannedFile(
                relative_path=relative.as_posix(),
                language=language,
                size_bytes=stat.st_size,
                modified_ns=stat.st_mtime_ns,
                content_hash=content_hash,
                content=raw.decode("utf-8", errors="replace"),
            ))
        revision_input = "\n".join(
            f"{item.relative_path}:{item.content_hash}" for item in files
        ).encode("utf-8")
        return ScanResult(
            root_path=str(source.root),
            revision=sha256(revision_input).hexdigest(),
            files=files,
            skipped=skipped,
        )
