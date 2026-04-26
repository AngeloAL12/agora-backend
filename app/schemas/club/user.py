from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    id: int
    name: str
    photo: str | None = None

    model_config = ConfigDict(from_attributes=True)
