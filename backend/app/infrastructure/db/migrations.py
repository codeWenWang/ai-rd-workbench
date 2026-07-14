from app.infrastructure.db.session import Database


def create_schema(database: Database) -> None:
    database.create_schema()
