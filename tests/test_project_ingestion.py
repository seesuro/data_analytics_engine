import hashlib
import threading

import pytest

from contracts import DatasetStatus
from ingestion.project_ingestion import ProjectIngestionService
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


def test_project_ingestion_saves_raw_file_and_ingests_to_project_db(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n2,West,200\n", encoding="utf-8")

    dataset = ProjectIngestionService(store).ingest_file(project.project_slug, source)

    assert dataset.status == DatasetStatus.READY
    assert dataset.project_id == project.project_id
    assert dataset.source_filename == "sales.csv"
    assert dataset.raw_path == store.raw_dir(project) / "sales.csv"
    assert dataset.raw_path.exists()
    assert dataset.table_name == "sales"
    assert dataset.row_count == 2
    assert dataset.content_hash == hashlib.sha256(source.read_bytes()).hexdigest()

    db = DBManager(str(store.project_db_path(project)))
    try:
        result = db.run_query("SELECT SUM(revenue) AS total_revenue FROM sales")
        assert result.loc[0, "total_revenue"] == 300

        metadata = DuckDBRegistry(db).metadata()
        assert metadata["tables"]["sales"]["row_count"] == 2
        assert set(metadata["tables"]["sales"]["columns"]) == {"order_id", "region", "revenue"}
    finally:
        db.close()


def test_project_ingestion_uses_unique_raw_path_for_duplicate_filename(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "sales.csv"
    source.write_text("Order ID,Region,Revenue\n1,East,100\n", encoding="utf-8")
    service = ProjectIngestionService(store)

    first = service.ingest_file(project.project_id, source)
    second = service.ingest_file(project.project_id, source)

    assert first.raw_path.name == "sales.csv"
    assert second.raw_path.name == "sales_2.csv"
    assert second.raw_path.exists()


def test_project_ingestion_raises_for_missing_source(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")

    with pytest.raises(FileNotFoundError):
        ProjectIngestionService(store).ingest_file(project.project_id, tmp_path / "missing.csv")


def test_project_ingestion_registers_failed_dataset(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    source = tmp_path / "notes.txt"
    source.write_text("not tabular", encoding="utf-8")

    dataset = ProjectIngestionService(store).ingest_file(project.project_id, source)

    assert dataset.status == DatasetStatus.FAILED
    assert dataset.error == "Unsupported file"

    db = DBManager(str(store.project_db_path(project)))
    try:
        datasets = DuckDBRegistry(db).list_datasets()
        assert datasets.loc[0, "status"] == "failed"
        assert datasets.loc[0, "error"] == "Unsupported file"
    finally:
        db.close()


def test_project_store_write_lock_serializes_access(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create_project("Retail Demo")
    observed: list[str] = []

    def worker(name: str) -> None:
        with store.write_lock(project):
            observed.append(f"{name}:start")
            observed.append(f"{name}:end")

    first = threading.Thread(target=worker, args=("first",))
    second = threading.Thread(target=worker, args=("second",))
    first.start()
    second.start()
    first.join()
    second.join()

    assert observed in [
        ["first:start", "first:end", "second:start", "second:end"],
        ["second:start", "second:end", "first:start", "first:end"],
    ]
