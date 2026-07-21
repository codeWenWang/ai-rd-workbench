from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath


@dataclass(slots=True)
class ProjectModuleInsight:
    name: str
    role: str
    file_count: int
    languages: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectEndpointInsight:
    method: str
    path: str
    handler: str
    source_path: str
    line_number: int
    framework: str
    module: str


@dataclass(slots=True)
class ProjectInsight:
    project_type: str
    modules: list[ProjectModuleInsight] = field(default_factory=list)
    endpoints: list[ProjectEndpointInsight] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class ProjectInsightBuilder:
    LOW_VALUE_DIRECTORIES = {
        ".github", ".gitlab", "docs", "doc", "test", "tests", "scripts",
        "examples", "example", "node_modules", "dist", "build", "target",
    }

    def build(self, files, routes, relations) -> ProjectInsight:
        files = list(files)
        routes = list(routes)
        relations = list(relations)
        file_by_id = {item.id: item for item in files}
        module_names, artifact_modules = self._maven_modules(files)
        if not module_names:
            module_names = self._top_level_modules(files)

        module_files = defaultdict(list)
        for item in files:
            module = self._module_for_path(item.relative_path, module_names)
            if module:
                module_files[module].append(item)

        dependencies = self._module_dependencies(files, module_names, artifact_modules)
        self._relation_dependencies(relations, module_names, dependencies)
        modules = [
            ProjectModuleInsight(
                name=name,
                role=_module_role(name),
                file_count=len(module_files[name]),
                languages=sorted({item.language for item in module_files[name]}),
                dependencies=sorted(dependencies[name]),
                evidence_paths=[
                    item.relative_path
                    for item in sorted(module_files[name], key=lambda file: (_evidence_priority(file), file.relative_path))[:2]
                ],
            )
            for name in sorted(module_names)
        ]

        endpoints = []
        seen_endpoints = set()
        for route in routes:
            source = file_by_id.get(route.project_file_id)
            if not source:
                continue
            key = (route.method, route.path, route.handler, source.relative_path, route.line_number)
            if key in seen_endpoints:
                continue
            seen_endpoints.add(key)
            endpoints.append(ProjectEndpointInsight(
                method=route.method,
                path=route.path,
                handler=route.handler,
                source_path=source.relative_path,
                line_number=route.line_number,
                framework=_framework(source),
                module=self._module_for_path(source.relative_path, module_names) or "应用",
            ))
        endpoints.sort(key=lambda item: (item.path, item.method, item.handler))
        entrypoints = sorted(
            item.relative_path for item in files if _is_entrypoint(item)
        )
        return ProjectInsight(
            project_type=_project_type(files, endpoints, bool(artifact_modules)),
            modules=modules,
            endpoints=endpoints,
            entrypoints=entrypoints,
            notes=[] if endpoints else ["当前静态分析未识别到可验证接口"],
        )

    def _maven_modules(self, files) -> tuple[list[str], dict[str, str]]:
        poms = {item.relative_path: _pom_data(item.content) for item in files if PurePosixPath(item.relative_path).name == "pom.xml"}
        root = poms.get("pom.xml")
        if not root or not root[1]:
            return [], {}
        modules = [name.strip("/") for name in root[1] if name.strip("/")]
        artifact_modules = {}
        for module in modules:
            artifact = poms.get(f"{module}/pom.xml", ("", [], []))[0]
            if artifact:
                artifact_modules[artifact] = module
        return modules, artifact_modules

    def _top_level_modules(self, files) -> list[str]:
        counts = Counter()
        for item in files:
            parts = PurePosixPath(item.relative_path).parts
            if len(parts) < 2 or parts[0].casefold() in self.LOW_VALUE_DIRECTORIES:
                continue
            counts[parts[0]] += 1
        return sorted(name for name, count in counts.items() if count > 0)

    @staticmethod
    def _module_for_path(path: str, module_names: list[str]) -> str:
        for name in sorted(module_names, key=len, reverse=True):
            if path == name or path.startswith(f"{name}/"):
                return name
        return ""

    def _module_dependencies(self, files, module_names, artifact_modules):
        dependencies = defaultdict(set)
        poms = {item.relative_path: _pom_data(item.content) for item in files if PurePosixPath(item.relative_path).name == "pom.xml"}
        for module in module_names:
            for artifact in poms.get(f"{module}/pom.xml", ("", [], []))[2]:
                target = artifact_modules.get(artifact)
                if target and target != module:
                    dependencies[module].add(target)
        return dependencies

    def _relation_dependencies(self, relations, module_names, dependencies) -> None:
        module_set = set(module_names)
        for relation in relations:
            source = self._module_for_path(relation.source_path, module_names)
            target = relation.target.removeprefix("./").split("/", 1)[0]
            if source and target in module_set and source != target:
                dependencies[source].add(target)


def _pom_data(content: str) -> tuple[str, list[str], list[str]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return "", [], []

    def children(element, name: str):
        return [child for child in element if child.tag.rsplit("}", 1)[-1] == name]

    artifact = next(((item.text or "").strip() for item in children(root, "artifactId")), "")
    modules = []
    modules_parent = next(iter(children(root, "modules")), None)
    if modules_parent is not None:
        modules = [(item.text or "").strip() for item in children(modules_parent, "module") if (item.text or "").strip()]
    dependencies = []
    dependencies_parent = next(iter(children(root, "dependencies")), None)
    if dependencies_parent is not None:
        for dependency in children(dependencies_parent, "dependency"):
            value = next(((item.text or "").strip() for item in children(dependency, "artifactId")), "")
            if value:
                dependencies.append(value)
    return artifact, modules, dependencies


def _module_role(name: str) -> str:
    value = name.casefold()
    if "ui" in value or "frontend" in value or "web" in value:
        return "界面"
    if value in {"server", "api", "app", "application", "gateway"} or "server" in value:
        return "入口服务"
    if "protocol" in value or "adapter" in value or "connector" in value:
        return "协议适配"
    if any(token in value for token in ("persistence", "database", "jdbc", "mysql", "postgres", "repository")):
        return "持久化"
    if any(token in value for token in ("storage", "blob", "s3")):
        return "存储"
    if any(token in value for token in ("core", "domain", "service")):
        return "核心"
    if "migration" in value:
        return "迁移"
    if "test" in value or "compat" in value:
        return "测试"
    return "功能模块"


def _framework(file) -> str:
    suffix = PurePosixPath(file.relative_path).suffix.casefold()
    if suffix == ".java":
        return "Spring MVC"
    if suffix == ".py":
        return "FastAPI"
    if suffix in {".js", ".mjs", ".cjs"}:
        return "Node.js"
    return file.language


def _is_entrypoint(file) -> bool:
    content = file.content
    return (
        "@SpringBootApplication" in content
        or "if __name__" in content
        or "FastAPI(" in content
        or ".listen(" in content
    )


def _evidence_priority(file) -> tuple[int, int]:
    path = file.relative_path.casefold()
    content = file.content
    if _is_entrypoint(file):
        return 0, len(path)
    if any(token in path for token in ("controller", "router", "service", "repository")):
        return 1, len(path)
    if PurePosixPath(path).name in {"pom.xml", "package.json", "pyproject.toml"}:
        return 2, len(path)
    return 3, len(path)


def _project_type(files, endpoints, has_maven_modules: bool) -> str:
    languages = {item.language for item in files}
    if has_maven_modules and "java" in languages:
        return "Java / Maven / Spring" if any(item.framework == "Spring MVC" for item in endpoints) else "Java / Maven"
    labels = []
    for language, label in (("python", "Python"), ("java", "Java"), ("javascript", "JavaScript")):
        if language in languages:
            labels.append(label)
    return " / ".join(labels) or "通用项目"
