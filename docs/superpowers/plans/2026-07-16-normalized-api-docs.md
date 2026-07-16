# Normalized API Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate standardized GET/POST/PUT/DELETE documentation with request and response examples inferred from scanned source code.

**Architecture:** Keep persisted routes unchanged and add a source-aware documentation analyzer at artifact generation time. The analyzer resolves controller methods and Java models from persisted project files, then the Markdown renderer formats only evidence-backed results.

**Tech Stack:** Python 3.11, FastAPI application layer, regex-based Java static analysis, pytest.

---

### Task 1: Define expected Spring API documentation

**Files:**
- Modify: `backend/tests/unit/projects/test_artifacts.py`

- [ ] Add a Spring controller, request DTO, response DTO and wrapper fixture.
- [ ] Assert normalized numbering, fields, request example and response JSON.
- [ ] Assert PATCH/HEAD and non-REST controllers are excluded.
- [ ] Run the focused test and confirm it fails with the current route-list renderer.

### Task 2: Add source-aware API analysis

**Files:**
- Modify: `backend/app/infrastructure/artifacts/api_docs.py`
- Modify: `backend/app/application/artifacts.py`
- Modify: `backend/app/infrastructure/projects/parsers.py`

- [ ] Pass scanned source files to the API documentation renderer.
- [ ] Resolve method signatures, parameter annotations and Java model fields.
- [ ] Generate conservative request and response examples.
- [ ] Filter unsupported methods and page controllers.
- [ ] Render the normalized Markdown structure.

### Task 3: Verify existing behavior

**Files:**
- Modify: `backend/tests/unit/projects/test_parsers.py`

- [ ] Cover extra method annotations around Spring mappings.
- [ ] Run project artifact and parser tests.
- [ ] Run the complete backend and frontend test suites.
- [ ] Regenerate the current Gitee project API document and inspect the result.
