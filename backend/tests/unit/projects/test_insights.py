from app.domain.entities import ProjectFile, ProjectRoute
from app.infrastructure.projects.insights import ProjectInsightBuilder


def project_file(file_id: str, path: str, language: str, content: str) -> ProjectFile:
    return ProjectFile(file_id, "project", path, language, "hash", content)


def test_maven_insight_groups_modules_roles_dependencies_and_endpoints() -> None:
    files = [
        project_file("root", "pom.xml", "xml", """
            <project><artifactId>demo</artifactId><modules>
              <module>core</module><module>storage-file</module><module>server</module>
            </modules></project>
        """),
        project_file("core-pom", "core/pom.xml", "xml", """
            <project><artifactId>demo-core</artifactId></project>
        """),
        project_file("storage-pom", "storage-file/pom.xml", "xml", """
            <project><artifactId>demo-storage-file</artifactId><dependencies>
              <dependency><artifactId>demo-core</artifactId></dependency>
            </dependencies></project>
        """),
        project_file("server-pom", "server/pom.xml", "xml", """
            <project><artifactId>demo-server</artifactId><dependencies>
              <dependency><artifactId>demo-core</artifactId></dependency>
              <dependency><artifactId>demo-storage-file</artifactId></dependency>
            </dependencies></project>
        """),
        project_file("app", "server/src/main/java/demo/DemoApplication.java", "java", """
            @SpringBootApplication public class DemoApplication { public static void main(String[] args) {} }
        """),
        project_file("controller", "server/src/main/java/demo/RepositoryController.java", "java", """
            @RestController class RepositoryController { @GetMapping("/items") String items() { return "ok"; } }
        """),
        project_file("service", "core/src/main/java/demo/RepositoryService.java", "java", "class RepositoryService {}"),
    ]
    routes = [
        ProjectRoute("route", "project", "controller", "GET", "/items", "RepositoryController.items", 2),
    ]

    insight = ProjectInsightBuilder().build(files, routes, [])

    modules = {module.name: module for module in insight.modules}
    assert list(modules) == ["core", "server", "storage-file"]
    assert modules["core"].role == "核心"
    assert modules["server"].role == "入口服务"
    assert modules["storage-file"].role == "存储"
    assert modules["server"].dependencies == ["core", "storage-file"]
    assert modules["storage-file"].dependencies == ["core"]
    assert insight.project_type == "Java / Maven / Spring"
    assert insight.entrypoints == ["server/src/main/java/demo/DemoApplication.java"]
    assert insight.endpoints[0].framework == "Spring MVC"
    assert insight.endpoints[0].module == "server"
    assert insight.endpoints[0].source_path.endswith("RepositoryController.java")


def test_insight_falls_back_to_high_value_top_level_directories() -> None:
    files = [
        project_file("docs", ".github/workflows/ci.yml", "yaml", "name: ci"),
        project_file("api", "backend/api.py", "python", "app = FastAPI()"),
        project_file("ui", "frontend/app.js", "javascript", "export function boot() {}"),
        project_file("readme", "README.md", "markdown", "# Demo"),
    ]

    insight = ProjectInsightBuilder().build(files, [], [])

    assert [module.name for module in insight.modules] == ["backend", "frontend"]
    assert insight.project_type == "Python / JavaScript"


def test_insight_deduplicates_equivalent_endpoints() -> None:
    files = [project_file("api", "server/Api.java", "java", "class Api {}")]
    duplicate = ProjectRoute("one", "project", "api", "GET", "/items", "Api.items", 10)
    routes = [duplicate, ProjectRoute("two", "project", "api", "GET", "/items", "Api.items", 10)]

    insight = ProjectInsightBuilder().build(files, routes, [])

    assert len(insight.endpoints) == 1
