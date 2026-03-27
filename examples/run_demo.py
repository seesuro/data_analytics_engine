# Example demo runner
from storage.db_manager import DBManager
from ingestion.data_ingestor import DataIngestor
from graph.analytics_graph import build_graph
from config.settings import DB_PATH
from state.analytics_state import AnalyticsState


def main():
    db = DBManager(DB_PATH)

    ingestor = DataIngestor(db)
    ingestor.ingest(["data/sample.csv"])

    graph = build_graph()

    state: AnalyticsState = {
    "user_query": "Total sales by region",
    "plan": "",
    "sql_query": "",
    "result": None
}
    result = graph.invoke(state)

    print(result)


if __name__ == "__main__":
    main()