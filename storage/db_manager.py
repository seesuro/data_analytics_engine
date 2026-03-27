import duckdb
import pandas as pd

class DBManager:
    def __init__(self, db_path: str):
        self.conn = duckdb.connect(db_path)

    def create_table(self, table_name: str, df: pd.DataFrame):
        self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        self.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")

    def run_query(self, query: str) -> pd.DataFrame:
        return self.conn.execute(query).fetchdf()

    def list_tables(self):
        return self.conn.execute("SHOW TABLES").fetchall()

    def describe_table(self, table_name: str):
        return self.conn.execute(f"DESCRIBE {table_name}").fetchdf()

    def close(self):
        self.conn.close()
