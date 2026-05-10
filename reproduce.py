from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
print("Testing GET /ai-analysis")
r = client.get("/ai-analysis/")
print(r.status_code)
