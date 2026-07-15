from pathlib import Path

from app.infrastructure.projects.scanner import LocalProjectScanner


def test_scanner_ignores_secrets_dependencies_and_binary_files(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run(): return 1", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("export default 1", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")

    result = LocalProjectScanner().scan(tmp_path)

    assert [item.relative_path for item in result.files] == ["app.py"]
    assert result.files[0].language == "python"
    assert result.revision


def test_scanner_revision_changes_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("value = 1", encoding="utf-8")
    scanner = LocalProjectScanner()
    first = scanner.scan(tmp_path)

    source.write_text("value = 2", encoding="utf-8")
    second = scanner.scan(tmp_path)

    assert first.revision != second.revision
    assert first.files[0].content_hash != second.files[0].content_hash


def test_scanner_collects_java_maven_and_runtime_configuration(tmp_path: Path) -> None:
    (tmp_path / "Application.java").write_text("class Application {}", encoding="utf-8")
    (tmp_path / "pom.xml").write_text("<project />", encoding="utf-8")
    (tmp_path / "application.properties").write_text("server.port=8080", encoding="utf-8")
    (tmp_path / "schema.sql").write_text("create table demo(id int);", encoding="utf-8")
    (tmp_path / "build.gradle").write_text("plugins { id 'java' }", encoding="utf-8")
    (tmp_path / "asset.jar").write_bytes(b"PK\x03\x04")

    result = LocalProjectScanner().scan(tmp_path)

    assert {item.relative_path for item in result.files} == {
        "Application.java", "application.properties", "build.gradle", "pom.xml", "schema.sql",
    }
    assert {item.language for item in result.files} == {
        "java", "properties", "gradle", "xml", "sql",
    }
