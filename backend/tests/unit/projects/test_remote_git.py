from pathlib import Path
from subprocess import CompletedProcess
import subprocess
import stat

import pytest

from app.domain.errors import ValidationError
from app.infrastructure.projects.remote_git import (
    RemoteGitRepositoryManager,
    normalize_repository_url,
)


@pytest.mark.parametrize(
    ("url", "source_type", "normalized", "owner", "name"),
    [
        (
            "https://github.com/openai/openai-python.git/",
            "github",
            "https://github.com/openai/openai-python.git",
            "openai",
            "openai-python",
        ),
        (
            "https://gitee.com/mirrors/flask",
            "gitee",
            "https://gitee.com/mirrors/flask.git",
            "mirrors",
            "flask",
        ),
    ],
)
def test_normalize_repository_url_accepts_public_github_and_gitee(
    url: str,
    source_type: str,
    normalized: str,
    owner: str,
    name: str,
) -> None:
    remote = normalize_repository_url(url, expected_source=source_type)

    assert remote.source_type == source_type
    assert remote.url == normalized
    assert remote.owner == owner
    assert remote.name == name


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/openai/openai-python",
        "git@github.com:openai/openai-python.git",
        "https://user:password@github.com/openai/openai-python",
        "https://github.com:8443/openai/openai-python",
        "https://github.com/openai/openai-python/issues",
        "https://github.com/openai/openai-python?tab=readme",
        "https://github.com/openai/openai-python#readme",
        "https://gitlab.com/openai/openai-python",
        "file:///tmp/repository",
    ],
)
def test_normalize_repository_url_rejects_unsafe_or_unsupported_urls(url: str) -> None:
    with pytest.raises(ValidationError, match="仓库地址"):
        normalize_repository_url(url)


def test_normalize_repository_url_rejects_source_mismatch() -> None:
    with pytest.raises(ValidationError, match="Gitee"):
        normalize_repository_url(
            "https://github.com/openai/openai-python",
            expected_source="gitee",
        )


def test_manager_clones_with_safe_arguments(tmp_path: Path) -> None:
    calls = []

    def runner(args, *, cwd, timeout):
        calls.append((list(args), cwd, timeout))
        target = Path(args[-1])
        target.mkdir(parents=True)
        (target / ".git").mkdir()
        return CompletedProcess(args, 0, stdout="", stderr="")

    manager = RemoteGitRepositoryManager(
        tmp_path / "cache",
        git_executable="git",
        runner=runner,
        clone_timeout_seconds=17,
    )

    remote = manager.clone(
        "https://gitee.com/mirrors/flask",
        expected_source="gitee",
    )

    assert remote.cache_path.is_dir()
    assert remote.cache_path.parent == (tmp_path / "cache").resolve()
    assert calls[0][0][:7] == [
        "git", "clone", "--depth", "1", "--single-branch", "--no-tags",
        "https://gitee.com/mirrors/flask.git",
    ]
    assert calls[0][1] == (tmp_path / "cache").resolve()
    assert calls[0][2] == 17


def test_manager_uses_source_only_partial_clone_for_github(tmp_path: Path) -> None:
    calls = []

    def runner(args, *, cwd, timeout):
        calls.append((list(args), Path(cwd), timeout))
        if "clone" in args:
            target = Path(args[-1])
            target.mkdir(parents=True)
            (target / ".git").mkdir()
        return CompletedProcess(args, 0, stdout="", stderr="")

    manager = RemoteGitRepositoryManager(
        tmp_path / "cache",
        git_executable="git",
        runner=runner,
        clone_timeout_seconds=17,
    )

    remote = manager.clone(
        "https://github.com/worstwoof/Music-Website",
        expected_source="github",
    )

    assert remote.cache_path.is_dir()
    assert calls[0][0][1:5] == [
        "-c", "http.version=HTTP/1.1", "clone", "--depth",
    ]
    assert "--filter=blob:none" in calls[0][0]
    assert "--no-checkout" in calls[0][0]
    assert calls[1][0][:4] == ["git", "sparse-checkout", "set", "--no-cone"]
    assert "*.py" in calls[1][0]
    assert "*.js" in calls[1][0]
    assert calls[2][0] == ["git", "checkout", "--force"]
    assert all(call[2] == 17 for call in calls)


def test_manager_retries_once_after_transient_clone_failure(tmp_path: Path) -> None:
    clone_attempts = 0

    def runner(args, *, cwd, timeout):
        nonlocal clone_attempts
        if "clone" in args:
            clone_attempts += 1
            target = Path(args[-1])
            if clone_attempts == 1:
                target.mkdir(parents=True)
                (target / "partial.lock").write_text("incomplete", encoding="utf-8")
                return CompletedProcess(args, 1, stdout="", stderr="proxy unavailable")
            target.mkdir(parents=True)
            (target / ".git").mkdir()
        return CompletedProcess(args, 0, stdout="", stderr="")

    manager = RemoteGitRepositoryManager(
        tmp_path / "cache",
        git_executable="git",
        runner=runner,
    )

    remote = manager.clone(
        "https://github.com/example/large-project",
        expected_source="github",
    )

    assert clone_attempts == 2
    assert remote.cache_path.is_dir()
    assert not (remote.cache_path / "partial.lock").exists()


def test_manager_update_falls_back_to_existing_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache" / "github-demo"
    (cache / ".git").mkdir(parents=True)

    def runner(args, *, cwd, timeout):
        return CompletedProcess(args, 1, stdout="", stderr="network unavailable")

    manager = RemoteGitRepositoryManager(
        tmp_path / "cache",
        git_executable="git",
        runner=runner,
    )

    assert manager.update(cache) == ["remote_update_unavailable"]


def test_manager_update_rejects_missing_or_broken_cache(tmp_path: Path) -> None:
    manager = RemoteGitRepositoryManager(
        tmp_path / "cache",
        git_executable="git",
        runner=lambda *args, **kwargs: None,
    )

    with pytest.raises(ValidationError, match="缓存"):
        manager.update(tmp_path / "cache" / "missing")


def test_manager_only_removes_directories_inside_cache_root(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    managed = cache_root / "github-demo"
    (managed / ".git").mkdir(parents=True)
    outside = tmp_path / "user-project"
    outside.mkdir()
    manager = RemoteGitRepositoryManager(cache_root, git_executable="git")

    manager.remove(managed)

    assert not managed.exists()
    with pytest.raises(ValidationError, match="缓存目录"):
        manager.remove(outside)
    assert outside.exists()


def test_manager_removes_read_only_git_pack_files(tmp_path: Path) -> None:
    managed = tmp_path / "cache" / "github-demo"
    pack = managed / ".git" / "objects" / "pack" / "pack.idx"
    pack.parent.mkdir(parents=True)
    pack.write_bytes(b"index")
    pack.chmod(stat.S_IREAD)
    manager = RemoteGitRepositoryManager(tmp_path / "cache", git_executable="git")

    manager.remove(managed)

    assert not managed.exists()


def test_git_runner_disables_interactive_credential_prompts(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        return CompletedProcess(args, 1, stdout="", stderr="authentication required")

    monkeypatch.setattr(subprocess, "run", fake_run)

    RemoteGitRepositoryManager._run(
        ["git", "ls-remote", "https://gitee.com/example/private.git"],
        cwd=tmp_path,
        timeout=10,
    )

    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert captured["env"]["GCM_INTERACTIVE"] == "Never"
