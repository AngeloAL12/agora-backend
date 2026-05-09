from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers.auth import auth_router, push_token_router, users_router
from app.routers.clubs import router as clubs_router
from app.routers.complaints import router as complaints_router
from app.routers.health import router as health_router
from app.routers.map import router as map_router
from app.routers.notifications import router as notifications_router
from app.services.redis_service import redis_chat_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Maneja el ciclo de vida de la aplicación FastAPI."""
    # Startup
    await redis_chat_manager.connect_redis()
    yield
    # Shutdown
    await redis_chat_manager.disconnect_redis()


app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.include_router(complaints_router)
app.include_router(health_router)
app.include_router(users_router)
app.include_router(push_token_router)
app.include_router(clubs_router)
app.include_router(map_router)
app.include_router(notifications_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    content_type = request.headers.get("content-type", "").lower()

    if (
        request.method == "POST"
        and request.url.path == "/complaints"
        and not content_type.startswith("multipart/form-data")
    ):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Content-Type inválido. Se requiere multipart/form-data.",
            },
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


@app.get("/")
def read_root():
    return {"message": "Welcome to the Agora API!"}


@app.get("/test")
def test_endpoint():
    return {"message": "This is a test endpoint."}
