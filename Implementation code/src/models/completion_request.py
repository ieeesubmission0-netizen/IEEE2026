from pydantic import BaseModel, Field


class CompleteRequest(BaseModel):
    complete_request: str = Field(
        description="a complete request in the form of a paragraph."
    )