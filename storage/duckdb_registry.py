import json

import pandas as pd

from contracts import Dataset, Run
from storage.db_manager import DBManager


class DuckDBRegistry:
    def __init__(self, db: DBManager):
        self.db = db

    def initialize(self) -> None:
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __datasets (
                dataset_id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                source_filename VARCHAR NOT NULL,
                content_hash VARCHAR NOT NULL,
                raw_path VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                uploaded_at TIMESTAMP NOT NULL,
                table_name VARCHAR,
                row_count BIGINT,
                error VARCHAR
            )
            """
        )
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __tables (
                dataset_id VARCHAR NOT NULL,
                table_name VARCHAR PRIMARY KEY,
                schema_json VARCHAR NOT NULL,
                row_count BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.db.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS __runs (
                run_id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                question VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                sql_json VARCHAR,
                result_preview_json VARCHAR,
                report VARCHAR,
                error VARCHAR,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP
            )
            """
        )

    def register_dataset(self, dataset: Dataset, schema: dict[str, str] | None = None) -> None:
        self.initialize()
        self.db.conn.execute(
            """
            INSERT OR REPLACE INTO __datasets (
                dataset_id,
                project_id,
                source_filename,
                content_hash,
                raw_path,
                status,
                uploaded_at,
                table_name,
                row_count,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(dataset.dataset_id),
                str(dataset.project_id),
                dataset.source_filename,
                dataset.content_hash,
                str(dataset.raw_path),
                dataset.status.value,
                dataset.uploaded_at,
                dataset.table_name,
                dataset.row_count,
                dataset.error,
            ],
        )

        if dataset.table_name and dataset.row_count is not None:
            table_schema = schema or self.table_schema(dataset.table_name)
            self.db.conn.execute(
                """
                INSERT OR REPLACE INTO __tables (
                    dataset_id,
                    table_name,
                    schema_json,
                    row_count
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    str(dataset.dataset_id),
                    dataset.table_name,
                    json.dumps(table_schema, sort_keys=True),
                    dataset.row_count,
                ],
            )

    def register_run(self, run: Run) -> None:
        self.initialize()
        self.db.conn.execute(
            """
            INSERT OR REPLACE INTO __runs (
                run_id,
                project_id,
                question,
                status,
                sql_json,
                result_preview_json,
                report,
                error,
                created_at,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(run.run_id),
                str(run.project_id),
                run.question,
                run.status.value,
                run.sql_run.model_dump_json() if run.sql_run else None,
                run.result_preview.model_dump_json() if run.result_preview else None,
                run.report,
                run.error,
                run.created_at,
                run.completed_at,
            ],
        )

    def list_datasets(self) -> pd.DataFrame:
        self.initialize()
        return self.db.run_query("SELECT * FROM __datasets ORDER BY uploaded_at")

    def list_registered_tables(self) -> pd.DataFrame:
        self.initialize()
        return self.db.run_query("SELECT * FROM __tables ORDER BY created_at")

    def list_runs(self) -> pd.DataFrame:
        self.initialize()
        return self.db.run_query("SELECT * FROM __runs ORDER BY created_at")

    def metadata(self) -> dict:
        tables = {}
        for row in self.list_registered_tables().to_dict(orient="records"):
            tables[row["table_name"]] = {
                "columns": json.loads(row["schema_json"]),
                "row_count": row["row_count"],
            }
        return {"tables": tables}

    def table_schema(self, table_name: str) -> dict[str, str]:
        described = self.db.describe_table(table_name)
        return {
            row["column_name"]: row["column_type"]
            for row in described[["column_name", "column_type"]].to_dict(orient="records")
        }
