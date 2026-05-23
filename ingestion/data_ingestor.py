import os
import pandas as pd
from pathlib import Path
from typing import List

from storage.db_manager import DBManager
from config.settings import METADATA_PATH

import json


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    return df


def infer_types(df: pd.DataFrame) -> pd.DataFrame:
    return df.convert_dtypes()


def detect_primary_key(df: pd.DataFrame):
    for col in df.columns:
        if df[col].is_unique and not df[col].isnull().any():
            return col
    return None


class MetadataManager:
    def __init__(self):
        self.metadata = {"tables": {}}

    def register(self, table_name: str, df: pd.DataFrame):
        self.metadata["tables"][table_name] = {
            "columns": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "primary_key": detect_primary_key(df),
            "row_count": len(df)
        }

    def save(self, path=METADATA_PATH):
        with open(path, "w") as f:
            json.dump(self.metadata, f, indent=2)


class DataIngestor:
    def __init__(self, db: DBManager):
        self.db = db
        self.meta = MetadataManager()

    def load_file(self, path: str) -> pd.DataFrame:
        if path.endswith(".csv"):
            return pd.read_csv(path)
        elif path.endswith(".xlsx"):
            return pd.read_excel(path)
        else:
            raise ValueError("Unsupported file")

    def table_name(self, path: str):
        return Path(path).stem.lower().replace(" ", "_")

    def ingest_file(self, path: str, table_name: str | None = None):
        df = self.load_file(path)
        df = normalize_column_names(df)
        df = infer_types(df)

        table = table_name or self.table_name(path)
        self.db.create_table(table, df)
        self.meta.register(table, df)
        return table, len(df)

    def ingest(self, files: List[str]):
        for f in files:
            if not os.path.exists(f):
                continue
            self.ingest_file(f)

        self.meta.save()

