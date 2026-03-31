from fastapi import FastAPI

from app.routers.auth import auth_router, push_token_router, users_router
from app.routers.health import router as health_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(users_router)
app.include_router(push_token_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Agora API!"}


@app.get("/test")
def test_endpoint():
    return {"message": "This is a test endpoint."}
