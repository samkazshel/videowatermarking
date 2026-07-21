from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str

class JobCreate(BaseModel):
    email: str

class JobResponse(BaseModel):
    id: int
    original_filename: str
    email: str
    status: str
    output_filename: str | None
    error_message: str | None
    created_at: str
    completed_at: str | None
