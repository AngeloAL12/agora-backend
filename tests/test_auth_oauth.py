from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.auth.role import Role  # Importamos el modelo de Rol

client = TestClient(app)


def test_read_root():
    """Prueba básica para asegurar que la API responde"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Agora API!"}


def test_read_users_me_unauthorized():
    """Prueba que /me falle si no hay token (Seguridad)"""
    response = client.get("/auth/me")
    assert response.status_code == 401


@patch("google.oauth2.id_token.verify_oauth2_token")
def test_google_login_success(mock_verify, db):
    """Simula un login exitoso de Google"""

    # --- PREPARAMOS LA BD DE PRUEBAS ---
    # Creamos el rol 'user' para que el servicio no lance el error 500
    if not db.query(Role).filter(Role.name == "user").first():
        db.add(Role(name="user"))  # <-- ¡Le quitamos la descripción!
        db.commit()
    # -----------------------------------

    # Configuramos el simulador de Google
    mock_verify.return_value = {
        "email": "test@itmexicali.edu.mx",
        "name": "Test User",
        "sub": "google-123",
    }

    response = client.post(
        "/auth/google/mobile-login", json={"token": "fake-google-token"}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["user"]["email"] == "test@itmexicali.edu.mx"


def test_google_login_invalid_domain():
    """Prueba que rechace correos que no son de la institución"""
    # Aquí podrías usar otro patch para simular un correo @gmail.com
    pass
