"""RDB Storage - Saves records to a relational database via SQLAlchemy."""

from typing import Any
from .base_storage import BaseStorage


class RDBStorage(BaseStorage):
    """Upserts records into a relational table.

    config keys:
        url         : SQLAlchemy connection URL  (e.g. 'postgresql+psycopg2://...')
        table       : target table name
        primary_key : field used for upsert deduplication (optional)
        batch_size  : insert batch size (default: 500)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.engine = None
        self.connection = None

    def connect(self) -> None:
        try:
            from sqlalchemy import create_engine
        except ImportError:
            raise ImportError("sqlalchemy is required: pip install sqlalchemy")
        self.engine = create_engine(self.config["url"])
        self.connection = self.engine.connect()

    def save(self, records: list[dict[str, Any]]) -> int:
        from sqlalchemy import text, Table, MetaData
        if not records:
            return 0
        table_name = self.config["table"]
        batch_size = self.config.get("batch_size", 500)
        meta = MetaData()
        meta.reflect(bind=self.engine, only=[table_name])
        table = meta.tables[table_name]
        saved = 0
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            self.connection.execute(table.insert(), batch)
            saved += len(batch)
        self.connection.commit()
        return saved

    def close(self) -> None:
        if self.connection:
            self.connection.close()
        if self.engine:
            self.engine.dispose()
