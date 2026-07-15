# Remote Git Project Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户能够连接公开 GitHub 或 Gitee 仓库，并复用现有项目扫描、问答和制品生成流程。

**Architecture:** 新增受控的远程 Git 仓库管理器，负责 URL 校验、浅克隆、更新回退和缓存清理。项目记录保存远程 URL 与本地缓存路径；扫描前准备远程缓存，准备完成后继续使用现有本地扫描器和分析链路。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Git CLI, Vanilla JavaScript, Node.js test runner, pytest

---

### Task 1: Remote repository URL and cache manager

**Files:**
- Create: `backend/app/infrastructure/projects/remote_git.py`
- Create: `backend/tests/unit/projects/test_remote_git.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Write failing URL validation tests**

Test `normalize_repository_url(url, expected_source)` with valid GitHub and Gitee URLs, optional `.git` suffix and trailing slash. Assert rejection of HTTP, SSH, credentials, ports, query strings, fragments, unsupported hosts, extra path segments and a selected source that does not match the host.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/projects/test_remote_git.py -q`

Expected: collection fails because `remote_git.py` does not exist.

- [ ] **Step 3: Implement URL normalization and cache naming**

Create `RemoteRepository` with `source_type`, `url`, `owner`, `name` and `cache_path`. Implement strict HTTPS parsing for `github.com` and `gitee.com`, safe owner/repository component validation and a stable cache directory containing a short SHA-256 suffix.

- [ ] **Step 4: Add failing clone, update and removal tests**

Inject a command runner into `RemoteGitRepositoryManager`. Assert clone uses argument arrays with `clone --depth 1 --single-branch --no-tags`, update uses `pull --ff-only`, update failure returns `remote_update_unavailable` when a valid `.git` cache exists, missing cache raises a validation error, and removal refuses paths outside the configured cache root.

- [ ] **Step 5: Implement Git command execution**

Use `shutil.which("git")` and `subprocess.run` without `shell=True`. Clone into a temporary directory and atomically rename it after success. Apply clone/update timeouts, translate failures to Chinese validation or external-service errors, and remove incomplete temporary directories.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/projects/test_remote_git.py -q`

Expected: all remote Git manager tests PASS.

### Task 2: Project persistence and application flow

**Files:**
- Modify: `backend/app/domain/entities.py`
- Modify: `backend/app/infrastructure/db/models.py`
- Modify: `backend/app/infrastructure/db/session.py`
- Modify: `backend/app/infrastructure/db/repositories.py`
- Modify: `backend/app/application/projects.py`
- Modify: `backend/app/dependencies.py`
- Modify: `backend/tests/unit/projects/test_project_repository.py`

- [ ] **Step 1: Write failing persistence tests**

Assert a project repository round-trips `source_type="github"`, the managed local `root_path` and normalized `source_uri`. Assert the schema migration adds `source_uri` to an existing `projects` table.

- [ ] **Step 2: Verify the persistence tests fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/projects/test_project_repository.py -q`

Expected: FAIL because `Project` and `ProjectModel` do not expose `source_uri`.

- [ ] **Step 3: Add the compatible database field**

Add nullable `source_uri` to the entity and SQLAlchemy model. Extend `Database.create_schema()` with a `PRAGMA table_info(projects)` guarded `ALTER TABLE`. Extend repository create and mapping while keeping local project calls compatible.

- [ ] **Step 4: Write failing use-case tests**

Use a fake remote manager to assert local creation still validates a directory, GitHub/Gitee creation clones before persistence, source mismatch errors propagate, prepare returns remote update warnings, and delete removes only remote managed caches.

- [ ] **Step 5: Implement the project use case and dependency wiring**

Extend `ProjectUseCase.create()` with `source_type`, `repository_url` and optional `root_path`. Add `prepare_for_scan(project_id)` and remote-aware deletion. Construct one `RemoteGitRepositoryManager` in `AppContainer` from `git_cache_dir`, `git_clone_timeout_seconds` and `git_update_timeout_seconds` settings.

- [ ] **Step 6: Run project unit tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/projects -q`

Expected: all project unit tests PASS.

### Task 3: Project API and cached scan fallback

**Files:**
- Modify: `backend/app/api/projects.py`
- Modify: `backend/tests/integration/test_project_api.py`

- [ ] **Step 1: Write failing API tests**

Assert the existing local payload remains valid. Add GitHub and Gitee payload tests that verify `source_type`, normalized `source_uri` and managed cache path. Assert scan combines `remote_update_unavailable` with semantic-index warnings and still returns scan counts when cached source exists.

- [ ] **Step 2: Verify API tests fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_project_api.py -q`

Expected: new remote project requests fail validation.

- [ ] **Step 3: Extend API schemas and scan preparation**

Make `root_path` and `repository_url` optional fields validated by the use case. Pass source fields to project creation. Before scanning, call `prepare_for_scan`, run existing analysis and vector indexing, and return de-duplicated warnings.

- [ ] **Step 4: Run integration tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_project_api.py -q`

Expected: local and remote project API tests PASS.

### Task 4: Frontend source selection and remote display

**Files:**
- Modify: `frontend/js/projects.js`
- Modify: `frontend/js/app.js`
- Modify: `frontend/index.html`
- Modify: `frontend/workbench.test.mjs`

- [ ] **Step 1: Add failing frontend source-contract tests**

Assert the project dialog exposes `source_type` options for local, GitHub and Gitee, uses `requiredWhen` for local path and repository URL fields, sends `repository_url`, and renders `source_uri` for remote project overview.

- [ ] **Step 2: Run frontend tests and verify RED**

Run: `node --test frontend/*.test.mjs`

Expected: new remote-source assertions FAIL.

- [ ] **Step 3: Implement the conditional connection dialog**

Add a source select. Keep the local absolute-path field for `local`; show a platform-specific public repository URL field for GitHub/Gitee. Send only visible fields through the existing dialog result mechanism. Display `GitHub · <URL>` or `Gitee · <URL>` in project overview.

- [ ] **Step 4: Bump project frontend asset versions**

Update `frontend/index.html`, `frontend/js/app.js` and imports of `projects.js` together so browsers do not retain the old project form.

- [ ] **Step 5: Run frontend tests and verify GREEN**

Run: `node --test frontend/*.test.mjs`

Expected: all frontend tests PASS.

### Task 5: Full verification and real repository smoke tests

**Files:**
- Modify only if verification exposes a defect in the scoped implementation.

- [ ] **Step 1: Run full automated tests**

Run: `node --test frontend/*.test.mjs`

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest tests -q`

Expected: all frontend and backend tests PASS.

- [ ] **Step 2: Verify Git and network prerequisites**

Run `git --version` and inspect the configured Git proxy without printing credentials. Confirm the cache directory is ignored by Git.

- [ ] **Step 3: Run real GitHub and Gitee smoke tests**

Start the app on an unused port with an isolated SQLite database and cache directory. Through the API or browser, connect one small public GitHub repository and one small public Gitee repository, scan them, verify files are listed, verify remote projects appear in the selector and project conversation grouping, then delete them and verify managed caches are removed.

- [ ] **Step 4: Browser-check desktop and mobile flows**

Verify the project source selector, conditional fields, error messages, overview source label, scan result and existing local-directory flow at desktop and mobile widths. Capture console errors and require none from application code.

- [ ] **Step 5: Review, commit, merge and push**

Run `git diff --check`, inspect the scoped diff, remove temporary databases, cache directories and screenshots, commit the implementation, merge it into `main`, rerun tests on the merged result and push `main` to `origin`.
