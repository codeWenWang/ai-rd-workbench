from app.infrastructure.projects.parsers import ParserRegistry


def test_python_parser_extracts_import_symbols_calls_and_fastapi_route() -> None:
    content = """
from fastapi import APIRouter
from app.application.projects import ProjectUseCase

router = APIRouter()

@router.get('/items')
def list_items():
    return ProjectUseCase.load()
"""

    parsed = ParserRegistry().parse("api.py", content)

    assert {item.name for item in parsed.symbols} >= {"list_items"}
    assert parsed.routes[0].method == "GET"
    assert parsed.routes[0].path == "/items"
    assert "app.application.projects" in parsed.imports
    assert "ProjectUseCase.load" in parsed.calls


def test_javascript_and_html_parsers_extract_references() -> None:
    registry = ParserRegistry()

    javascript = registry.parse("app.js", "import { api } from './api.js'; export function boot() {}")
    html = registry.parse("index.html", '<script src="js/app.js"></script><link href="css/style.css">')

    assert javascript.imports == ["./api.js"]
    assert {item.name for item in javascript.symbols} == {"boot"}
    assert html.imports == ["js/app.js", "css/style.css"]
