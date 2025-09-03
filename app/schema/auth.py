from pydantic import BaseModel, EmailStr


class RegisterUser(BaseModel):
    email: EmailStr
    password: str
