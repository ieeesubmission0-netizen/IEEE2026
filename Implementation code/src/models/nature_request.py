from enum import Enum
from pydantic import BaseModel


class RequestCategory(str, Enum):
    BUSINESS = "business"
    SERVICE_INCOMPLETE = "service_incomplete"
    SERVICE_COMPLETE = "service_complete"


class CategorizedRequest(BaseModel):
    category: RequestCategory
