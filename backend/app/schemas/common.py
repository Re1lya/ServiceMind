from pydantic import BaseModel


class BaseResponse(BaseModel):
    """Shared API response schema."""

    message: str


# TODO: add standard pagination and error response schemas.
