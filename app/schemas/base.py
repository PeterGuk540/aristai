from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with ORM mode enabled for all response schemas."""

    model_config = ConfigDict(from_attributes=True)
