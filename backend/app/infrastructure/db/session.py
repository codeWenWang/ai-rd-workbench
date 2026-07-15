from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///"):
            path = Path(database_url.removeprefix("sqlite:///"))
            path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        )
        self.session_factory = sessionmaker(
            bind=self.engine, class_=Session, expire_on_commit=False
        )

    def create_schema(self) -> None:
        from app.infrastructure.db.models import Base

        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            conversation_columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(conversations)")
            }
            if "project_id" not in conversation_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE conversations ADD COLUMN project_id VARCHAR(36)"
                )
            project_columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(projects)")
            }
            if "source_uri" not in project_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE projects ADD COLUMN source_uri VARCHAR(1000)"
                )
            message_columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(messages)")
            }
            if "metadata_json" not in message_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE messages ADD COLUMN metadata_json TEXT DEFAULT '{}'"
                )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_conversations_project_id "
                "ON conversations(project_id)"
            )
            connection.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5("
                "chunk_id UNINDEXED, content, title, category, resource_type UNINDEXED, "
                "tokenize='unicode61')"
            )
            connection.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS project_chunks_fts USING fts5("
                "chunk_id UNINDEXED, project_id UNINDEXED, content, relative_path, "
                "tokenize='unicode61')"
            )


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    module = type(dbapi_connection).__module__
    if not module.startswith("sqlite3"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
