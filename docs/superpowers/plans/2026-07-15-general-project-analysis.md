# General Project Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace FastAPI-only project artifacts with module-oriented analysis and add a runnable Java/Maven/Spring first version.

**Architecture:** Extend the existing scanner and parser registry, then build an in-memory normalized `ProjectInsight` from persisted files, routes, and relations. Artifact renderers consume this model so diagrams are framework-neutral and module-level without a database migration.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, regex/XML static analysis, Mermaid, Node test runner, pytest.

---

### Task 1: Scan and parse Java/Maven projects

**Files:**
- Modify: `backend/app/infrastructure/projects/scanner.py`
- Modify: `backend/app/infrastructure/projects/parsers.py`
- Test: `backend/tests/unit/projects/test_project_scanner.py`
- Test: `backend/tests/unit/projects/test_project_parsers.py`

- [ ] Add failing scanner tests asserting `.java`, `pom.xml`, `.properties`, and `.sql` are collected while binary files remain ignored.
- [ ] Run `pytest tests/unit/projects/test_project_scanner.py -q` and confirm the new assertions fail because the extensions are unsupported.
- [ ] Extend `LANGUAGES` with Java, XML, Properties, SQL, and Gradle text extensions.
- [ ] Add failing parser tests for Java imports/types and Spring mappings combining class-level and method-level paths.
- [ ] Run `pytest tests/unit/projects/test_project_parsers.py -q` and confirm Java routes are absent.
- [ ] Implement `JavaSourceParser` with conservative package/import/type/annotation parsing and register it for `.java`.
- [ ] Implement `MavenPomParser` that records module/dependency artifact IDs as relations and register root/module `pom.xml` files.
- [ ] Run both test modules and confirm they pass.

### Task 2: Build a normalized project insight model

**Files:**
- Create: `backend/app/infrastructure/projects/insights.py`
- Test: `backend/tests/unit/projects/test_project_insights.py`

- [ ] Write failing tests constructing Maven root/module POM files and asserting modules, roles, dependencies, entrypoints, endpoints, and framework names.
- [ ] Run `pytest tests/unit/projects/test_project_insights.py -q` and confirm imports fail because the insight builder does not exist.
- [ ] Add dataclasses `ProjectModuleInsight`, `ProjectEndpointInsight`, and `ProjectInsight`.
- [ ] Implement `ProjectInsightBuilder.build(files, routes, relations)` with Maven module extraction, top-level fallback grouping, role classification, dependency mapping, endpoint framework detection, and deterministic node limits.
- [ ] Run the insight tests and confirm they pass.

### Task 3: Replace artifact renderers with insight-based output

**Files:**
- Modify: `backend/app/application/artifacts.py`
- Modify: `backend/app/infrastructure/artifacts/mermaid.py`
- Modify: `backend/app/infrastructure/artifacts/api_docs.py`
- Modify: `backend/app/infrastructure/artifacts/__init__.py`
- Test: `backend/tests/integration/test_project_analysis.py`

- [ ] Add failing artifact tests for a miniature Java/Maven/Spring project asserting architecture contains module names, flow/sequence omit `FastAPI`, and API docs contain Spring routes.
- [ ] Run `pytest tests/integration/test_project_analysis.py -q` and confirm the new expectations fail.
- [ ] Construct `ProjectInsight` once in `ArtifactUseCase.generate` and pass it to each renderer.
- [ ] Render architecture by module role and dependency, limiting low-value nodes.
- [ ] Render a framework-neutral representative flow and sequence with explicit evidence-based fallback.
- [ ] Render framework-neutral API docs including framework and source location.
- [ ] Run the integration tests and confirm they pass.

### Task 4: Update the project analysis interface wording

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/js/artifacts.js`
- Modify: `frontend/workbench.test.mjs`

- [ ] Add failing frontend assertions that descriptions no longer promise FastAPI-only API behavior and empty states use framework-neutral wording.
- [ ] Run `node --test workbench.test.mjs` and confirm the new assertions fail.
- [ ] Update architecture, flow, sequence, and API document descriptions to describe module structure, core paths, representative interactions, and detected interfaces.
- [ ] Bump the frontend cache version consistently for changed modules.
- [ ] Run the frontend tests and syntax checks.

### Task 5: Real-project verification and regression

**Files:**
- No production files unless verification exposes a defect.

- [ ] Run `pytest -q` from `backend` and confirm all tests pass.
- [ ] Run `node --test workbench.test.mjs` and JavaScript syntax checks from `frontend`.
- [ ] Rescan cached `gitee-kailing-kkRepo-56fa4f9161` and confirm Java is the dominant language, Spring routes are detected, and the four artifacts contain meaningful project-specific content.
- [ ] Open the app in a browser, generate all four artifacts, and verify diagrams render without overlap or Mermaid errors at desktop and mobile widths.
- [ ] Run `git diff --check` and review the final diff for unrelated changes.
