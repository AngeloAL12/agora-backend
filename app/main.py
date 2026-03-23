from fastapi import FastAPI

from app.routers.health import router as health_router

app = FastAPI()

app.include_router(health_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Agora API!"}


@app.get("/test")
def test_endpoint():
    return {"message": "This is a test endpoint."}
