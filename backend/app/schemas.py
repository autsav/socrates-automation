from datetime import datetime
from pydantic import BaseModel


class Receipt(BaseModel):
    id: str
    user_id: str
    filename: str
    content_type: str
    size: int
    storage_path: str
    url: str
    created_at: datetime
