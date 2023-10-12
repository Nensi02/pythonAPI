from sqlalchemy import Column, Integer, String, Boolean, MetaData, Table, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from alembic import op
import sqlalchemy as sa

class User(Base):
    __tablename__ = 'users'

    def __str__(self):
        return self.username

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50))
    
    user_id = relationship("Post", back_populates = "username")

class Post(Base):
    __tablename__ = 'posts'

    def __str__(self):
        return self.content

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(50))
    content = Column(String(100))
    user_id = Column(Integer, ForeignKey('users.id'))

    username = relationship("User", back_populates = "user_id")

class FileData(Base):
    __tablename__ = 'filedata'
    
    id = Column(Integer, primary_key = True, index = True)
    filename = Column(String(255))
    filesize = Column(Integer)
    filetype = Column(String(50))

class Login(Base):
    __tablename__ = "logins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(25), unique=True, index=True)
    password = Column(String(20))
