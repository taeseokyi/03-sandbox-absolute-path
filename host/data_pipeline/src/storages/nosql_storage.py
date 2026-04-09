"""NoSQL Storage - Saves records to MongoDB."""

from typing import Any
from .base_storage import BaseStorage


class NoSQLStorage(BaseStorage):
    """Inserts or upserts records into a MongoDB collection.

    config keys:
        uri         : MongoDB connection URI  (e.g. 'mongodb://localhost:27017')
        database    : target database name
        collection  : target collection name
        upsert_key  : field used as filter for upsert (optional)
        batch_size  : insert batch size (default: 500)
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = None
        self.col = None

    def connect(self) -> None:
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError("pymongo is required: pip install pymongo")
        self.client = MongoClient(self.config["uri"])
        db = self.client[self.config["database"]]
        self.col = db[self.config["collection"]]

    def save(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        upsert_key = self.config.get("upsert_key")
        batch_size = self.config.get("batch_size", 500)
        saved = 0
        if upsert_key:
            from pymongo import UpdateOne
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                ops = [
                    UpdateOne({upsert_key: r[upsert_key]}, {"$set": r}, upsert=True)
                    for r in batch
                ]
                result = self.col.bulk_write(ops)
                saved += result.upserted_count + result.modified_count
        else:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                result = self.col.insert_many(batch)
                saved += len(result.inserted_ids)
        return saved

    def close(self) -> None:
        if self.client:
            self.client.close()
