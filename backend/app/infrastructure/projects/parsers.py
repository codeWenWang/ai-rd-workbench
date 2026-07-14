from __future__ import annotations

import ast
import re
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

    def parse(self, relative_path: str, content: str) -> ParsedFile:
        imports = [match.group("path") for match in self.IMPORT_RE.finditer(content)]
        symbols = [
            ParsedSymbol(match.group("name"), "function", content.count("\n", 0, match.start()) + 1)
            for match in self.FUNCTION_RE.finditer(content)
        ]
        return ParsedFile(relative_path, "javascript", _unique(imports), symbols)


class HtmlReferenceParser:
    SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=['\"](?P<path>[^'\"]+)['\"]", re.I)
    LINK_RE = re.compile(r"<link\b[^>]*\bhref=['\"](?P<path>[^'\"]+)['\"]", re.I)

    def parse(self, relative_path: str, content: str) -> ParsedFile:
        imports = [match.group("path") for match in self.SCRIPT_RE.finditer(content)]
        imports.extend(match.group("path") for match in self.LINK_RE.finditer(content))
        return ParsedFile(relative_path, "html", _unique(imports))


class PlainTextParser:
    def parse(self, relative_path: str, content: str) -> ParsedFile:
        language = Path(relative_path).suffix.casefold().lstrip(".") or "text"
        return ParsedFile(relative_path, language)


class ParserRegistry:
    def __init__(self) -> None:
        self.python = PythonAstParser()
        self.javascript = JavaScriptModuleParser()
        self.html = HtmlReferenceParser()
        self.plain = PlainTextParser()

    def parse(self, relative_path: str, content: str) -> ParsedFile:
        suffix = Path(relative_path).suffix.casefold()
        if suffix == ".py":
            return self.python.parse(relative_path, content)
        if suffix in {".js", ".mjs", ".cjs"}:
            return self.javascript.parse(relative_path, content)
        if suffix in {".html", ".htm"}:
            return self.html.parse(relative_path, content)
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
