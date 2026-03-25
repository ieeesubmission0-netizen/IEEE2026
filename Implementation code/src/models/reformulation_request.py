from pydantic import BaseModel, Field


class ReformulatedRequest(BaseModel):
    reformulated_request: str = Field(
        description="Complete technical request rewritten from the user request in the form of a paragraph."
    )