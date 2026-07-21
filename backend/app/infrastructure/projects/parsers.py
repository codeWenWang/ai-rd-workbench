from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ParsedSymbol:
    name: str
    kind: str
    line_number: int
    end_line_number: int | None = None


@dataclass(slots=True)
class ParsedRoute:
    method: str
    path: str
    handler: str
    line_number: int


@dataclass(slots=True)
class ParsedFile:
    relative_path: str
    language: str
    imports: list[str] = field(default_factory=list)
    symbols: list[ParsedSymbol] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    routes: list[ParsedRoute] = field(default_factory=list)
    package: str = ""
    module_name: str = ""
    modules: list[str] = field(default_factory=list)


class PythonAstParser:
    ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}

    def parse(self, relative_path: str, content: str) -> ParsedFile:
        parsed = ParsedFile(relative_path, "python")
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return parsed
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                parsed.imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    parsed.imports.append(node.module)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                parsed.symbols.append(ParsedSymbol(
                    node.name, kind, node.lineno, getattr(node, "end_lineno", None)
                ))
                parsed.routes.extend(self._routes(node))
            elif isinstance(node, ast.Call):
                name = _dotted_name(node.func)
                if name:
                    parsed.calls.append(name)
        parsed.imports = _unique(parsed.imports)
        parsed.calls = _unique(parsed.calls)
        parsed.symbols.sort(key=lambda item: (item.line_number, item.name))
        parsed.routes.sort(key=lambda item: (item.line_number, item.path))
        return parsed

    def _routes(self, node) -> list[ParsedRoute]:
        routes = []
        for decorator in getattr(node, "decorator_list", []):
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr.casefold()
            if method not in self.ROUTE_METHODS or not decorator.args:
                continue
            path = decorator.args[0]
            if isinstance(path, ast.Constant) and isinstance(path.value, str):
                routes.append(ParsedRoute(method.upper(), path.value, node.name, node.lineno))
        return routes


class JavaScriptModuleParser:
    IMPORT_RE = re.compile(
        r"(?:import\s+(?:[^;]*?\s+from\s+)?|require\s*\()"
        r"['\"](?P<path>[^'\"]+)['\"]"
    )
    FUNCTION_RE = re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)"
    )
    FETCH_RE = re.compile(
        r"\bfetch\s*\(\s*(['\"])(?P<path>/[^'\"]*)\1(?P<options>[^)]*)\)",
        re.S,
    )
    CLIENT_RE = re.compile(
        r"\b(?:axios|api|http)\.(?P<method>get|post|put|delete)\s*"
        r"\(\s*(['\"])(?P<path>/[^'\"]*)\2",
        re.I,
    )

    def parse(self, relative_path: str, content: str) -> ParsedFile:
        imports = [match.group("path") for match in self.IMPORT_RE.finditer(content)]
        symbols = [
            ParsedSymbol(match.group("name"), "function", content.count("\n", 0, match.start()) + 1)
            for match in self.FUNCTION_RE.finditer(content)
        ]
        routes = []
        for match in self.FETCH_RE.finditer(content):
            method_match = re.search(r"\bmethod\s*:\s*['\"](GET|POST|PUT|DELETE)['\"]", match.group("options"), re.I)
            method = method_match.group(1).upper() if method_match else "GET"
            routes.append(ParsedRoute(
                method, match.group("path"), "前端 fetch 请求",
                content.count("\n", 0, match.start()) + 1,
            ))
        for match in self.CLIENT_RE.finditer(content):
            routes.append(ParsedRoute(
                match.group("method").upper(), match.group("path"), "前端 HTTP 客户端请求",
                content.count("\n", 0, match.start()) + 1,
            ))
        language = "typescript" if Path(relative_path).suffix.casefold() in {".ts", ".tsx"} else "javascript"
        return ParsedFile(relative_path, language, _unique(imports), symbols, routes=routes)


class HtmlReferenceParser:
    SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=['\"](?P<path>[^'\"]+)['\"]", re.I)
    LINK_RE = re.compile(r"<link\b[^>]*\bhref=['\"](?P<path>[^'\"]+)['\"]", re.I)

    def parse(self, relative_path: str, content: str) -> ParsedFile:
        imports = [match.group("path") for match in self.SCRIPT_RE.finditer(content)]
        imports.extend(match.group("path") for match in self.LINK_RE.finditer(content))
        return ParsedFile(relative_path, "html", _unique(imports))


class JavaSourceParser:
    PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*;", re.M)
    IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([^;]+)\s*;", re.M)
    TYPE_RE = re.compile(r"\b(class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
    CLASS_BLOCK_RE = re.compile(
        r"(?P<annotations>(?:\s*@[A-Za-z_$][\w$.]*(?:\s*\([^)]*\))?\s*)*)"
        r"(?:public\s+|protected\s+|private\s+|abstract\s+|final\s+|sealed\s+)*"
        r"(?:class|interface|record)\s+(?P<name>[A-Za-z_$][\w$]*)",
        re.M,
    )
    METHOD_RE = re.compile(
        r"(?P<annotations>(?:\s*@[A-Za-z_$][\w$.]*(?:\s*\([^)]*\))?\s*)+)"
        r"(?:public\s+|protected\s+|private\s+|static\s+|final\s+|synchronized\s+|default\s+)*"
        r"(?:<[^>]+>\s*)?[A-Za-z_$][\w$<>,.?\[\] ]*\s+(?P<name>[A-Za-z_$][\w$]*)\s*\(",
        re.M,
    )
    MAPPING_RE = re.compile(
        r"@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)"
        r"(?:\s*\((?P<args>[^)]*)\))?"
    )
    CALL_RE = re.compile(r"\b([A-Z][A-Za-z0-9_$]*(?:\.[A-Za-z_$][\w$]*)+)\s*\(")
    METHODS = {
        "GetMapping": "GET", "PostMapping": "POST", "PutMapping": "PUT",
        "PatchMapping": "PATCH", "DeleteMapping": "DELETE",
    }

    def parse(self, relative_path: str, content: str) -> ParsedFile:
        package_match = self.PACKAGE_RE.search(content)
        package = package_match.group(1) if package_match else ""
        imports = _unique(match.group(1).strip() for match in self.IMPORT_RE.finditer(content))
        symbols = [
            ParsedSymbol(match.group(2), match.group(1), content.count("\n", 0, match.start()) + 1)
            for match in self.TYPE_RE.finditer(content)
        ]
        class_match = self.CLASS_BLOCK_RE.search(content)
        class_name = class_match.group("name") if class_match else Path(relative_path).stem
        class_prefix = ""
        if class_match:
            mappings = self._mappings(class_match.group("annotations"), default_method="")
            if mappings:
                class_prefix = mappings[0][1]
        routes = []
        for match in self.METHOD_RE.finditer(content):
            mappings = self._mappings(match.group("annotations"))
            if not mappings:
                continue
            method_name = match.group("name")
            line_number = content.count("\n", 0, match.start()) + 1
            symbols.append(ParsedSymbol(method_name, "method", line_number))
            for method, path in mappings:
                routes.append(ParsedRoute(
                    method, _join_route_paths(class_prefix, path),
                    f"{class_name}.{method_name}", line_number,
                ))
        symbols.sort(key=lambda item: (item.line_number, item.name))
        routes.sort(key=lambda item: (item.line_number, item.path, item.method))
        calls = _unique(match.group(1) for match in self.CALL_RE.finditer(content))
        return ParsedFile(
            relative_path, "java", imports, symbols, calls, routes, package=package,
        )

    def _mappings(self, annotations: str, *, default_method: str = "ANY") -> list[tuple[str, str]]:
        mappings = []
        for match in self.MAPPING_RE.finditer(annotations):
            annotation = match.group(1)
            args = match.group("args") or ""
            paths = _mapping_paths(args)
            if annotation == "RequestMapping":
                methods = re.findall(r"RequestMethod\.([A-Z]+)", args) or [default_method]
            else:
                methods = [self.METHODS[annotation]]
            for method in methods:
                for path in paths:
                    mappings.append((method, path))
        return mappings


class MavenPomParser:
    def parse(self, relative_path: str, content: str) -> ParsedFile:
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return ParsedFile(relative_path, "xml")

        def children(element, name: str):
            return [child for child in element if child.tag.rsplit("}", 1)[-1] == name]

        artifact = next((item.text or "" for item in children(root, "artifactId")), "").strip()
        modules = []
        modules_parent = next(iter(children(root, "modules")), None)
        if modules_parent is not None:
            modules = [(item.text or "").strip() for item in children(modules_parent, "module") if (item.text or "").strip()]
        dependencies = []
        dependencies_parent = next(iter(children(root, "dependencies")), None)
        if dependencies_parent is not None:
            for dependency in children(dependencies_parent, "dependency"):
                dependency_artifact = next(
                    ((item.text or "").strip() for item in children(dependency, "artifactId")), ""
                )
                if dependency_artifact:
                    dependencies.append(f"maven:{dependency_artifact}")
        return ParsedFile(
            relative_path, "xml", imports=_unique(dependencies),
            module_name=artifact, modules=_unique(modules),
        )


class PlainTextParser:
    def parse(self, relative_path: str, content: str) -> ParsedFile:
        language = Path(relative_path).suffix.casefold().lstrip(".") or "text"
        return ParsedFile(relative_path, language)


class ParserRegistry:
    def __init__(self) -> None:
        self.python = PythonAstParser()
        self.javascript = JavaScriptModuleParser()
        self.html = HtmlReferenceParser()
        self.java = JavaSourceParser()
        self.maven = MavenPomParser()
        self.plain = PlainTextParser()

    def parse(self, relative_path: str, content: str) -> ParsedFile:
        suffix = Path(relative_path).suffix.casefold()
        if suffix == ".py":
            return self.python.parse(relative_path, content)
        if suffix in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".vue"}:
            return self.javascript.parse(relative_path, content)
        if suffix in {".html", ".htm"}:
            return self.html.parse(relative_path, content)
        if suffix == ".java":
            return self.java.parse(relative_path, content)
        if Path(relative_path).name.casefold() == "pom.xml":
            return self.maven.parse(relative_path, content)
        return self.plain.parse(relative_path, content)


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _join_route_paths(prefix: str, path: str) -> str:
    parts = [item.strip("/") for item in (prefix, path) if item and item != "/"]
    return "/" + "/".join(parts) if parts else "/"


def _mapping_paths(args: str) -> list[str]:
    explicit = re.search(
        r"(?:value|path)\s*=\s*(\{[^}]*\}|['\"][^'\"]*['\"])",
        args,
    )
    if explicit:
        expression = explicit.group(1)
    else:
        stripped = args.strip()
        if stripped.startswith("{") and "}" in stripped:
            expression = stripped[:stripped.index("}") + 1]
        elif stripped.startswith(("'", '"')):
            quote = stripped[0]
            closing = stripped.find(quote, 1)
            expression = stripped[:closing + 1] if closing > 0 else ""
        else:
            expression = ""
    values = [match.group(2) for match in re.finditer(r"(['\"])(.*?)\1", expression)]
    return values or [""]
