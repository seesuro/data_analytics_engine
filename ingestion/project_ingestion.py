import hashlib
import shutil
from pathlib import Path
from uuid import UUID

from contracts import Dataset, DatasetStatus
from ingestion.data_ingestor import DataIngestor
from storage.db_manager import DBManager
from storage.duckdb_registry import DuckDBRegistry
from storage.project_store import ProjectStore


class ProjectIngestionService:
    def __init__(self, project_store: ProjectStore):
        self.project_store = project_store

    def ingest_file(self, project_id_or_slug: str | UUID, source_path: str | Path) -> Dataset:
        project = self.project_store.get_project(project_id_or_slug)
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Upload source does not exist: {source}")

        content_hash = self._sha256(source)
        dataset = Dataset(
            project_id=project.project_id,
            source_filename=source.name,
            content_hash=content_hash,
            raw_path=self.project_store.raw_dir(project) / source.name,
        )

        with self.project_store.write_lock(project):
            dataset.raw_path = self._unique_raw_path(dataset.raw_path)
            shutil.copy2(source, dataset.raw_path)
            db = DBManager(str(self.project_store.project_db_path(project)))
            try:
                ingestor = DataIngestor(db)
                table_name = ingestor.table_name(source.name)
                table_name, row_count = ingestor.ingest_file(str(dataset.raw_path), table_name=table_name)
                dataset.table_name = table_name
                dataset.row_count = row_count
                dataset.status = DatasetStatus.READY
                DuckDBRegistry(db).register_dataset(dataset)
            except Exception as exc:
                dataset.status = DatasetStatus.FAILED
                dataset.error = str(exc)
                DuckDBRegistry(db).register_dataset(dataset)
            finally:
                db.close()

        return dataset

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _unique_raw_path(path: Path) -> Path:
        if not path.exists():
            return path

        counter = 2
        while True:
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1
