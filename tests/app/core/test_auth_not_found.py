from fastapi.testclient import TestClient
from app.main import app
from tests.test_setup import insert_role, insert_user

client = TestClient(app)

def test_get_current_user_invalid_token():
    # Token no convertible a int
    response = client.post(
        "/push-token",
        json={"push_token": "abc"},
        headers={"Authorization": "Bearer notanumber"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido"

def test_get_current_user_user_not_found():
    insert_role()
    insert_user(id=1)
    # Token válido pero usuario inexistente
    response = client.post(
        "/push-token",
        json={"push_token": "abc"},
        headers={"Authorization": "Bearer 9999"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Usuario no existe"
