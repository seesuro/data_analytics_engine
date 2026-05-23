import pandas as pd

from ingestion.data_ingestor import DataIngestor
from storage.db_manager import DBManager


def test_ingest_file_normalizes_and_persists_metadata(tmp_path, monkeypatch):
    csv_path = tmp_path / "Sales Data.csv"
    csv_path.write_text("Order ID,Region,Revenue\n1,East,100\n2,West,200\n", encoding="utf-8")

    db_path = tmp_path / "test.duckdb"
    db = DBManager(str(db_path))

    metadata_path = tmp_path / "metadata.json"
    monkeypatch.setattr("ingestion.data_ingestor.METADATA_PATH", str(metadata_path))

    try:
        ingestor = DataIngestor(db)
        ingestor.ingest_file(str(csv_path))
        ingestor.meta.save(str(metadata_path))

        # Table name is derived from the filename
        assert "sales_data" in ingestor.meta.metadata["tables"]

        columns = ingestor.meta.metadata["tables"]["sales_data"]["columns"]
        assert set(columns.keys()) == {"order_id", "region", "revenue"}

        # Data is actually in DuckDB
        out = db.run_query("SELECT SUM(revenue) AS total_revenue FROM sales_data")
        assert out.loc[0, "total_revenue"] == 300

        assert metadata_path.exists()
    finally:
        db.close()
