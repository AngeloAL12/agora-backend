from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import get_db

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Welcome to the Agora API!"}


@app.get("/test")
def test_endpoint():
    return {"message": "This is a test endpoint."}


@app.get("/health/db")
def health_check_db():
    """
    Check database connection health.
    Returns connection status and basic database information.
    """
    db = None
    try:
        db = next(get_db())
        # Execute a simple query to verify connection
        result = db.execute(text("SELECT 1")).scalar()

        if result == 1:
            # Get database dialect and driver info
            engine = db.get_bind()
            dialect = engine.dialect.name if engine else "unknown"
            driver = getattr(engine, "driver", "unknown") if engine else "unknown"

            return {
                "status": "healthy",
                "database": "connected",
                "details": {"dialect": dialect, "driver": driver},
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={"status": "unhealthy", "database": "query failed"},
            )
    except OperationalError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "connection failed",
                "error": str(e),
            },
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "database": "unknown error", "error": str(e)},
        ) from None
    finally:
        if db:
            db.close()
