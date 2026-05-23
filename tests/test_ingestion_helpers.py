from ingestion.data_ingestor import DataIngestor
from storage.db_manager import DBManager


def test_load_file_rejects_unsupported_extension(tmp_path):
    db = DBManager(str(tmp_path / "t.duckdb"))
    try:
        ingestor = DataIngestor(db)
        try:
            ingestor.load_file(str(tmp_path / "x.txt"))
        except ValueError as e:
            assert "Unsupported file" in str(e)
        else:
            raise AssertionError("Expected ValueError")
    finally:
        db.close()


def test_table_name_normalization(tmp_path):
    db = DBManager(str(tmp_path / "t.duckdb"))
    try:
        ingestor = DataIngestor(db)
        assert ingestor.table_name("My File Name.csv") == "my_file_name"
    finally:
        db.close()

