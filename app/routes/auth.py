import json
import uuid
from uuid import uuid4

import random
import os
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File,Request,status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from app.database import get_db
from app.models import User, DocumentMeta, Folder, ChatHistory
from app.auth import hash_password, verify_user, get_current_user
from app.redis_cache import get_redis
from app.schemas import UserResponse, UserCreate, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest, OTPVerificationRequest, FolderCreate, DocumentResponse, ChatHistoryResponse,FolderResponse,QueryDocumentRequest
from app.utils import send_reset_email, send_otp_email
from redis.asyncio import Redis
from app.config import s3_client, BUCKET_NAME,openai_api_key
import tempfile
from dotenv import load_dotenv
from fastapi.responses import FileResponse,StreamingResponse
from botocore.exceptions import ClientError
from unstructured.documents import elements
from io import BytesIO

# from langchain.embeddings import OpenAIEmbeddings
# from langchain.vectorstores import FAISS
# from langchain.chains import RetrievalQA
# from langchain.llms import OpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain_community.llms import OpenAI
# from langchain import  Document
# from langchain import LangChainIndex
# from langchain.indexes import LangChainIndex
from langchain.document_loaders import UnstructuredPDFLoader  
from langchain.chains import RetrievalQA
from langchain.agents import Agent
from langchain_community.document_loaders import S3FileLoader
from pdf2image import convert_from_path
from langchain.document_loaders import PyPDFLoader
import re
# import pytesseract
# pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'

import pytesseract
from PIL import Image
import logging
# Set the Tesseract command path
os.environ['OCR_AGENT'] = '/opt/homebrew/bin/tesseract' 
embeddings = OpenAIEmbeddings(api_key=openai_api_key)


load_dotenv()

router = APIRouter()

# Register
@router.post("/register/")
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    existing_user = await db.execute(select(User).where(User.email == user.email))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(name=user.name, email=user.email, password=hash_password(user.password))
    db.add(new_user)
    await db.commit()
    otp = str(random.randint(100000, 999999))
    await redis.set(f"otp:{user.email}", otp, ex=300)

    if send_otp_email(user.email, otp):
        return {"message": "User registered successfully. Please verify your OTP."}
    else:
        raise HTTPException(status_code=500, detail="Failed to send OTP")



# Verify OTP
@router.post("/verify-registration-otp/")
async def verify_registration_otp(data: OTPVerificationRequest, redis=Depends(get_redis)):
    email = data.email
    otp = data.otp

    stored_otp = await redis.get(f"otp:{email}")

    if stored_otp and stored_otp.decode('utf-8') == otp:
        await redis.delete(f"otp:{email}")
        return {"message": "OTP verified successfully. Registration complete."}
    
    raise HTTPException(status_code=400, detail="Invalid or expired OTP")



@router.post("/login/")
async def login(
    request: Request, 
    login_data: LoginRequest, 
    db: AsyncSession = Depends(get_db), 
    redis: Redis = Depends(get_redis)
):
    user = await verify_user(login_data.email, login_data.password, db)
    if user:

        session_id = str(uuid.uuid4())
        await redis.set(session_id, user.id, ex=3600) 

       
        request.session["session_id"] = session_id

        response = Response(content={"message": "Login successful"})
        response.set_cookie(
            key="session_id",
            value=session_id,
            samesite="None",  
            secure=True       
        )
        return response

    raise HTTPException(status_code=400, detail="Invalid credentials")


#check-login
@router.get("/check-login/")
async def check_login_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    try:
        user = await get_current_user(request, db, redis)
        return {"status": "Logged in", "user_id": user.id, "email": user.email}
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            return {"status": "Not logged in"}
        raise e



# User logout
@router.post("/logout/")
async def logout_user(request: Request, redis: Redis = Depends(get_redis)):
    session_id = request.session.get("session_id")
    if session_id:
        await redis.delete(session_id) 
    return {"message": "Logout successful"}



# Forgot password
@router.post("/forgot-password/")
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    email = request.email 
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    reset_session_id = str(uuid.uuid4())
    await redis.set(f"reset_session:{reset_session_id}", user.id, ex=3600)

    email_sent = send_reset_email(email, reset_session_id)
    if email_sent:
        return {"message": "Password reset email sent."}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")



# Reset password
@router.post("/reset-password/")
async def reset_password(request: ResetPasswordRequest, redis=Depends(get_redis), db: AsyncSession = Depends(get_db)):
    reset_session_id = request.reset_session_id
    new_password = request.new_password

    user_id = await redis.get(f"reset_session:{reset_session_id}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired session")

    user_id = int(user_id)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password = hash_password(new_password)
    await db.commit()
    await redis.delete(f"reset_session:{reset_session_id}")

    return {"message": "Password reset successfully."}



# List users
@router.get("/users/", response_model=List[UserResponse])
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users



# Delete user
@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return {"message": f"User with ID {user_id} deleted successfully"}
def create_index_from_document(document_meta: DocumentMeta):
    try:
        index_name = document_meta.file_key.split('/')[-1]  
        print(f"Creating index for {document_meta.file_name} with key {document_meta.file_key}")
        return index_name
    except Exception as e:
        print(f"Failed to create index for {document_meta.file_name}: {str(e)}")
        raise


#upload Document
@router.post("/upload-document/")
async def upload_document(
    file: UploadFile = File(...),  
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_key = f"documents/{str(uuid4())}_{file.filename}"

    try:
        file_content = await file.read()

        # Upload to S3
        s3_client.put_object(Bucket=BUCKET_NAME, Key=file_key, Body=file_content, ContentType="application/pdf")
        document_meta = DocumentMeta(
            file_name=file.filename,
            file_key=file_key,
            owner_id=current_user.id
        )
        db.add(document_meta)
        await db.commit()
        
        # Create index after successful upload
        index = create_index_from_document(document_meta)

        return {"message": "Document uploaded successfully", "file_key": file_key}

    except Exception as e:
        logging.error(f"Error during document upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")



#view-document
@router.get("/documents-view/")
async def view_documents(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is not available")

    try:
        result = await db.execute(select(DocumentMeta).filter(DocumentMeta.owner_id == current_user.id, DocumentMeta.folder_id.is_(None)))
        documents = result.scalars().all()

        document_list = [{
            "id": doc.id,
            "file_name": doc.file_name,
            "file_key": doc.file_key,
            "file_metadata": json.loads(doc.file_metadata) if doc.file_metadata else {},
        } for doc in documents]

        return document_list

    except Exception as e:
        logging.error(f"Error fetching documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




# Create folder
@router.post("/folders/", response_model=FolderResponse)
async def create_folder(folder: FolderResponse, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing_folder = await db.execute(
        select(Folder).where(Folder.name == folder.name, Folder.user_id == current_user.id)
    )
    if existing_folder.scalars().first():
        raise HTTPException(status_code=400, detail="Folder with this name already exists")

    new_folder = Folder(name=folder.name, user_id=current_user.id)
    db.add(new_folder)
    await db.commit()
    await db.refresh(new_folder)
    
    return new_folder


#view-folder
@router.get("/folders-view/", response_model=List[FolderCreate])
async def get_folders(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Folder).where(Folder.user_id == current_user.id))
    folders = result.scalars().all()
    return folders


# Document handling within folders
@router.post("/folders/{folder_id}/documents/", response_model=DocumentResponse)
async def upload_document_to_folder(folder_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    folder = await db.execute(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id))
    if not folder.scalars().first():
        raise HTTPException(status_code=404, detail="Folder not found")

    file_extension = file.filename.split('.')[-1]
    if file_extension not in ["pdf", "ppt", "csv"]:
        raise HTTPException(status_code=400, detail="Unsupported file format")

    file_key = f"documents/{folder_id}/{str(uuid4())}_{file.filename}"

    file_content = await file.read()
    file_metadata = {"file_type": file_extension, "file_size": len(file_content)}

    document = DocumentMeta(folder_id=folder_id, file_name=file.filename, file_key=file_key, metadata=json.dumps(file_metadata))
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return document

 #list documnts in the folder

@router.get("/folders/{folder_id}/documents/", response_model=List[DocumentResponse])
async def get_documents_in_folder(folder_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    folder = await db.execute(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id))
    if not folder.scalars().first():
        raise HTTPException(status_code=404, detail="Folder not found")

    documents = await db.execute(select(DocumentMeta).where(DocumentMeta.folder_id == folder_id))
    documents_list = documents.scalars().all()

    return documents_list


#move document to the folder
@router.patch("/folders/{folder_id}/documents/{document_id}")
async def move_document(
    folder_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    folder = await db.execute(select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id))
    if not folder.scalars().first():
        raise HTTPException(status_code=404, detail="Folder not found")

    result = await db.execute(select(DocumentMeta).where(DocumentMeta.id == document_id, DocumentMeta.owner_id == current_user.id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.folder_id = folder_id
    await db.commit()

    index = update_index_for_document(document)

    return {"detail": "Document moved successfully!"}




#opening the folder for Q&a
@router.get("/documents/{document_id}/")
async def read_document(
    document_id: int, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    document = await db.execute(
        select(DocumentMeta).where(DocumentMeta.id == document_id, DocumentMeta.owner_id == current_user.id)
    )
    doc = document.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_key = doc.file_key

    try:
        s3_object = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        pdf_stream = s3_object['Body']
        
        headers = {
            "Content-Disposition": f'inline; filename="{doc.file_name}"',
            "Content-Type": "application/pdf"
        }
        
        return StreamingResponse(pdf_stream, media_type='application/pdf', headers=headers)
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail=f"File not found at key: {file_key}")
    except Exception as e:
        logging.error(f"Error fetching document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving the file.")


def create_index_from_document(document_meta):

    pass

def update_index_for_document(document_meta):

    pass

async def process_document(file_key):

    try:
        s3_object = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        pdf_stream = s3_object['Body'].read()  
        pdf_file = BytesIO(pdf_stream)
        loader = PyPDFLoader(pdf_file)
        documents = loader.load()  
        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)
        embeddings = OpenAIEmbeddings()  
        vectorstore = FAISS.from_documents(chunks, embeddings)

        return vectorstore
    except ClientError as e:
        logging.error(f"Error fetching document from S3: {e}")
        raise HTTPException(status_code=500, detail="Error fetching document from S3.")
    except Exception as e:
        logging.error(f"Error processing document: {e}")
        raise HTTPException(status_code=500, detail="Error processing document.")

async def generate_answer_from_documents(documents: List, question: str) -> str:
    keywords = re.findall(r'\w+', question.lower())
    answer_found = False
    answer = ""

    for doc in documents:
        doc_text = doc.text if hasattr(doc, 'text') else str(doc)

    
        if any(keyword in doc_text.lower() for keyword in keywords):
            answer_found = True
            relevant_sentences = extract_relevant_information(doc_text, keywords)
            answer = f"{relevant_sentences}"
            break  

    if not answer_found:
        answer = "No relevant information found related to your question."

    return answer

def extract_relevant_information(doc_text: str, keywords: List[str]) -> str:
    sentences = doc_text.split('. ')
    relevant_sentences = []

    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in keywords):
            relevant_sentences.append(sentence.strip())

    return ' '.join(relevant_sentences[:3]) if relevant_sentences else "No specific details found."



#query-document
@router.post("/query-document/")
async def query_document(
    request: QueryDocumentRequest,
    db: AsyncSession = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    document = await db.execute(
        select(DocumentMeta.file_name, DocumentMeta.file_key).where(DocumentMeta.id == request.document_id)
    )
    doc = document.fetchone()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name, file_key = doc
    try:
        s3_object = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        pdf_stream = s3_object['Body']
        
        pdf_bytes = BytesIO(pdf_stream.read())
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_bytes.getvalue())
            temp_file_path = temp_file.name
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()  
        os.remove(temp_file_path)
        answer = await generate_answer_from_documents(documents, request.question)

        return {"answer": answer}

    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail=f"File not found at key: {file_key}")
    except Exception as e:
        logging.error(f"Error processing document {request.document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=" occurred while retrieving the file.")