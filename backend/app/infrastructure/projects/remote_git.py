from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from app.domain.errors import ExternalServiceError, ValidationError
from app.infrastructure.projects.scanner import LANGUAGES


_HOST_SOURCES = {"github.com": "github", "gitee.com": "gitee"}
_SOURCE_LABELS = {"github": "GitHub", "gitee": "Gitee"}
_PATH_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SOURCE_PATTERNS = tuple(sorted(f"*{suffix}" for suffix in LANGUAGES))
_CLONE_ATTEMPTS = 2
CommandRunner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True, slots=True)
class RemoteRepository:
    source_type: str
    url: str
    owner: str
    name: str
    cache_path: Path | None = None


def normalize_repository_url(
    url: str,
    expected_source: str | None = None,
) -> RemoteRepository:
    raw = (url or "").strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("仓库地址格式不正确") from exc
    host = (parsed.hostname or "").casefold()
    source_type = _HOST_SOURCES.get(host)
    parts = parsed.path.strip("/").split("/") if parsed.path.strip("/") else []
    if (
        parsed.scheme.casefold() != "https"
        or source_type is None
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or len(parts) != 2
    ):
        raise ValidationError("仓库地址格式不正确，仅支持公开 GitHub 或 Gitee HTTPS 地址")
    owner, repository = parts
    if repository.casefold().endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository or not _PATH_COMPONENT.fullmatch(owner) or not _PATH_COMPONENT.fullmatch(repository):
        raise ValidationError("仓库地址格式不正确")
    if expected_source and expected_source != source_type:
        expected = _SOURCE_LABELS.get(expected_source, expected_source)
        raise ValidationError(f"仓库地址不是 {expected} 仓库")
    return RemoteRepository(
        source_type=source_type,
        url=f"https://{host}/{owner}/{repository}.git",
        owner=owner,
        name=repository,
    )


class RemoteGitRepositoryManager:
    def __init__(
        self,
        cache_root: str | Path,
        *,
        git_executable: str | None = None,
        runner: CommandRunner | None = None,
        clone_timeout_seconds: int = 180,
        update_timeout_seconds: int = 90,
    ) -> None:
        self.cache_root = Path(cache_root).expanduser().resolve()
        self.git_executable = git_executable or shutil.which("git")
        self.runner = runner or self._run
        self.clone_timeout_seconds = clone_timeout_seconds
        self.update_timeout_seconds = update_timeout_seconds

    def clone(self, url: str, *, expected_source: str | None = None) -> RemoteRepository:
        remote = normalize_repository_url(url, expected_source)
        target = self._cache_path(remote)
        if self._valid_cache(target):
            return replace(remote, cache_path=target)
        self._require_git()
        self.cache_root.mkdir(parents=True, exist_ok=True)
        if target.exists():
            _remove_tree(target)
        temporary = self.cache_root / f".clone-{uuid4().hex}"
        args = [self.git_executable]
        if remote.source_type == "github":
            args.extend(["-c", "http.version=HTTP/1.1"])
        args.extend([
            "clone", "--depth", "1", "--single-branch", "--no-tags",
        ])
        if remote.source_type == "github":
            args.extend(["--filter=blob:none", "--no-checkout"])
        args.extend([remote.url, str(temporary)])
        try:
            cloned = False
            for _ in range(_CLONE_ATTEMPTS):
                if temporary.exists():
                    _remove_tree(temporary, ignore_errors=True)
                result = self.runner(
                    args,
                    cwd=self.cache_root,
                    timeout=self.clone_timeout_seconds,
                )
                if result.returncode == 0 and self._valid_cache(temporary):
                    cloned = True
                    break
            if not cloned:
                raise ExternalServiceError("无法克隆公开仓库，请检查仓库地址、网络或 Git 代理")
            if remote.source_type == "github":
                sparse = self.runner(
                    [self.git_executable, "sparse-checkout", "set", "--no-cone", *_SOURCE_PATTERNS],
                    cwd=temporary,
                    timeout=self.clone_timeout_seconds,
                )
                checkout = self.runner(
                    [self.git_executable, "checkout", "--force"],
                    cwd=temporary,
                    timeout=self.clone_timeout_seconds,
                )
                if sparse.returncode != 0 or checkout.returncode != 0:
                    raise ExternalServiceError("无法检出仓库源码，请检查网络或 Git 代理")
            temporary.replace(target)
            return replace(remote, cache_path=target)
        except subprocess.TimeoutExpired as exc:
            raise ExternalServiceError("克隆仓库超时，请检查网络或 Git 代理") from exc
        except OSError as exc:
            raise ExternalServiceError("无法执行 Git，请确认 Git 已安装且缓存目录可写") from exc
        finally:
            if temporary.exists():
                _remove_tree(temporary, ignore_errors=True)

    def update(self, cache_path: str | Path) -> list[str]:
        target = self._managed_path(cache_path)
        if not self._valid_cache(target):
            raise ValidationError("远程项目缓存不存在或已损坏，请重新连接项目")
        if not self.git_executable:
            return ["remote_update_unavailable"]
        try:
            result = self.runner(
                [self.git_executable, "pull", "--ff-only"],
                cwd=target,
                timeout=self.update_timeout_seconds,
            )
            return [] if result.returncode == 0 else ["remote_update_unavailable"]
        except (OSError, subprocess.TimeoutExpired):
            return ["remote_update_unavailable"]

    def remove(self, cache_path: str | Path) -> None:
        target = self._managed_path(cache_path)
        if target.exists():
            _remove_tree(target)

    def _cache_path(self, remote: RemoteRepository) -> Path:
        digest = sha256(remote.url.encode("utf-8")).hexdigest()[:10]
        name = f"{remote.source_type}-{remote.owner}-{remote.name}-{digest}"
        return (self.cache_root / name).resolve()

    def _managed_path(self, value: str | Path) -> Path:
        target = Path(value).expanduser().resolve()
        if target == self.cache_root or not target.is_relative_to(self.cache_root):
            raise ValidationError("目标不是受控的远程项目缓存目录")
        return target

    @staticmethod
    def _valid_cache(path: Path) -> bool:
        return path.is_dir() and (path / ".git").is_dir()

    def _require_git(self) -> None:
        if not self.git_executable:
            raise ExternalServiceError("Git 未安装或无法执行")

    @staticmethod
    def _run(
        args: Sequence[str],
        *,
        cwd: Path,
        timeout: int,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            list(args),
            cwd=str(cwd),
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GCM_INTERACTIVE": "Never",
            },
        )


def _remove_tree(path: Path, *, ignore_errors: bool = False) -> None:
    def clear_readonly(function, value, error_info):
        try:
            Path(value).chmod(stat.S_IREAD | stat.S_IWRITE)
            function(value)
        except OSError:
            if not ignore_errors:
                raise error_info[1]

    try:
        shutil.rmtree(path, onerror=clear_readonly)
    except OSError:
        if not ignore_errors:
            raise
