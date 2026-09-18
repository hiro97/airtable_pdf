from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "po" in data["supported_documents"]
    print("Health check passed, supported docs:", data["supported_documents"])

def test_download_file():
    response = client.get("/files/download/ZOO_Korea_김애정_2026-07.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    print("File download check passed!")

def test_webhook_endpoints():
    # Test valid doc_type missing body
    res1 = client.post("/webhook/po", json={})
    assert res1.status_code == 400
    assert "Missing record_id" in res1.json()["detail"]

    # Test legacy po webhook
    res2 = client.post("/webhook/generate-po", json={})
    assert res2.status_code == 400

    # Test unknown doc_type (should 404)
    res3 = client.post("/webhook/non_existent_doc", json={"record_id": "rec123"})
    assert res3.status_code == 404
    print("Webhook endpoint checks passed!")

if __name__ == "__main__":
    test_health()
    test_download_file()
    test_webhook_endpoints()
    print("All multi-document API tests passed successfully!")
