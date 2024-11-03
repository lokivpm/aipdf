from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import func

Base = declarative_base()
#user
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String(255), unique=True, index=True)
    password = Column(String(255))
    documents = relationship("DocumentMeta", back_populates="owner", cascade="all, delete-orphan")
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")

#folder
class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="folders")
    documents = relationship("DocumentMeta", back_populates="folder", cascade="all, delete-orphan")
    chats = relationship("ChatHistory", back_populates="folder", cascade="all, delete-orphan")

#Document
class DocumentMeta(Base):
    __tablename__ = 'document_meta'

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, index=True)
    file_key = Column(String, unique=True)
    file_metadata = Column(JSON)
    content_summary = Column(String)
    owner_id = Column(Integer, ForeignKey('users.id'))
    folder_id = Column(Integer, ForeignKey('folders.id'))

    owner = relationship("User", back_populates="documents")
    folder = relationship("Folder", back_populates="documents")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#Chat history
class ChatHistory(Base):
    __tablename__ = 'chat_history'

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey('folders.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    message = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    folder = relationship("Folder", back_populates="chats")
    user = relationship("User", back_populates="chats")
