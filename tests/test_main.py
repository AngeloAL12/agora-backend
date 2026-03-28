from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_root():
    """Prueba el endpoint raíz '/' que ahora devuelve el mensaje de bienvenida."""
    response = client.get("/")
    assert response.status_code == 200
    # Verificamos que el JSON coincida exactamente con tu app/main.py
    assert response.json() == {"message": "Welcome to the Agora API!"}


# El endpoint '/test' fue eliminado en tu versión más reciente de main.py,
# por lo que eliminamos su prueba para evitar el error 404.
