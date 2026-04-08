import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ingestor = DataIngestor(db_manager)
# ingestor.ingest_file("data/sales.csv")

from ingestion.data_ingestor import DataIngestor
from storage.db_manager import DBManager
import json
from config.settings import METADATA_PATH

db_path = "data/analytics.db"
db_manager = DBManager(db_path)
ingestor = DataIngestor(db_manager)
ingestor.ingest_file("data/sales.csv")
ingestor.meta.save()  # Ensure metadata is saved after ingestion

# Load metadata if available
if os.path.exists(METADATA_PATH):
    with open(METADATA_PATH, "r") as f:
        metadata = json.load(f)
else:
    metadata = {}


from graph.analytics_graph import build_graph

graph = build_graph()



query = "What is the total revenue by region?"

initial_state = {
    "user_query": query,
    "db": db_manager,
    "metadata": metadata
}

result = graph.invoke(initial_state)

print("\nFINAL OUTPUT:")
print(result)