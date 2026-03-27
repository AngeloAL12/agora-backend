from fastapi import FastAPI

from app.routers import push_token
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.users import router as users_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(users_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the Agora API!"}


@app.get("/test")
def test_endpoint():
    return {"message": "This is a test endpoint."}


app.include_router(push_token.router)
