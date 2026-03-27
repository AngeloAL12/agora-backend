from fastapi import FastAPI
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router # Si tienes uno de salud

app = FastAPI(title="Agora API")

# Solo incluimos los routers necesarios
app.include_router(auth_router)
app.include_router(health_router)

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de Agora"}