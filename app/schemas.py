#schemas.py
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class OTPVerificationRequest(BaseModel):
    email: str
    otp: str



class LoginRequest(BaseModel):
    email: str
    password: str



class ForgotPasswordRequest(BaseModel):
    email: str

    
class ResetPasswordRequest(BaseModel):
    reset_session_id: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str



class FolderCreate(BaseModel):
    id: int  
    name: str

class FolderResponse(BaseModel):

    name: str    


class DocumentResponse(BaseModel):
    id: int
    file_name: str
    file_key: str



class ChatHistoryResponse(BaseModel):
    id: int
    folder_id: int
    user_id: int
    message: str
    created_at: str 


class QuestionAnswerResponse(BaseModel):
    question: str
    answer: str

class QueryDocumentRequest(BaseModel):
    document_id: int
    question: str



class Config:
    orm_mode = True    