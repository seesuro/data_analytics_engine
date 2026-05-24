import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingestion.project_ingestion import ProjectIngestionService
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


def main() -> None:
    store = ProjectStore(ROOT / "var" / "example_projects")
    project = store.create_project(
        project_name="Example Ingestion Demo",
        project_slug=f"example-ingestion-{uuid4().hex[:8]}",
    )

    dataset = ProjectIngestionService(store).ingest_file(project.project_slug, ROOT / "data" / "sales.csv")

    db = DBManager(str(store.project_db_path(project)))
    try:
        metadata = DuckDBRegistry(db).metadata()
    finally:
        db.close()

    print("PROJECT")
    print(f"  name: {project.project_name}")
    print(f"  slug: {project.project_slug}")
    print(f"  path: {project.path}")
    print()
    print("DATASET")
    print(f"  source: {dataset.source_filename}")
    print(f"  status: {dataset.status}")
    print(f"  table: {dataset.table_name}")
    print(f"  rows: {dataset.row_count}")
    print()
    print("METADATA")
    print(metadata)


if __name__ == "__main__":
    main()
