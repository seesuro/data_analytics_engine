import pandas as pd

from storage.db_manager import DBManager


def test_db_manager_create_and_query(tmp_path):
    db_path = tmp_path / "test.duckdb"
    db = DBManager(str(db_path))
    try:
        df = pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})
        db.create_table("t1", df)

        out = db.run_query("SELECT COUNT(*) AS n FROM t1")
        assert out.loc[0, "n"] == 3
    finally:
        db.close()

