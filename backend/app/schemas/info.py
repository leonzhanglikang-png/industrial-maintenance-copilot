from pydantic import BaseModel


class InfoResponse(BaseModel):
    name: str
    purpose: str
    safety_notice: str
