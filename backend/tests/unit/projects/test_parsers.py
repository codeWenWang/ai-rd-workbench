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


def test_java_parser_extracts_types_imports_and_spring_routes() -> None:
    content = """
package com.example.server;

import com.example.core.RepositoryService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/repository/{name}")
public class RepositoryContentController {
    @GetMapping("/**")
    public String download() {
        return RepositoryService.load();
    }

    @RequestMapping(value = "/status", method = RequestMethod.HEAD)
    public void status() {}
}
"""

    parsed = ParserRegistry().parse("server/RepositoryContentController.java", content)

    assert parsed.package == "com.example.server"
    assert "com.example.core.RepositoryService" in parsed.imports
    assert {item.name for item in parsed.symbols} >= {"RepositoryContentController", "download", "status"}
    assert [(route.method, route.path, route.handler) for route in parsed.routes] == [
        ("GET", "/repository/{name}/**", "RepositoryContentController.download"),
        ("HEAD", "/repository/{name}/status", "RepositoryContentController.status"),
    ]


def test_maven_parser_extracts_modules_and_internal_dependencies() -> None:
    content = """
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <artifactId>kkrepo-server</artifactId>
  <modules><module>core</module><module>server</module></modules>
  <dependencies>
    <dependency><groupId>com.github.klboke</groupId><artifactId>kkrepo-core</artifactId></dependency>
  </dependencies>
</project>
"""

    parsed = ParserRegistry().parse("pom.xml", content)

    assert parsed.module_name == "kkrepo-server"
    assert parsed.modules == ["core", "server"]
    assert "maven:kkrepo-core" in parsed.imports
