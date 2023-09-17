import os
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, Form, File
from pydantic import BaseModel, Field
from typing import Annotated, Optional
import models
import aiofiles
import uuid
from database import engine, SessionLocal
from sqlalchemy.orm import Session

app = FastAPI()
BASEDIR = os.path.dirname(__file__)
models.Base.metadata.create_all(bind=engine)

class PostBase(BaseModel):
    title: str = Field(max_length = 50, min_length = 2)
    content: str = Field(max_length = 50, min_length = 2)
    user_id: int = Field(gt = 0)
    images: str

class UserBase(BaseModel):
    name: str = Field(max_length = 50, min_length = 2)

async def handle_image(image: UploadFile) -> str:
    filenames, ext = os.path.splitext(image.filename)
    directory = os.path.join(BASEDIR, 'images/')
    if not os.path.exists(directory):
        os.makedirs(directory)
    contentData = await image.read()
    if image.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=406, detail="Only .jpeg or .png  files allowed")
    elif image.size > 200000:
        raise HTTPException(status_code=406, detail = 'Image size must be less than 2 MB')
    filename = image.filename
    async with aiofiles.open(os.path.join(directory, filename), mode = 'wb') as file:
        await file.write(contentData)
    return filename

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

@app.post('/posts/', status_code=status.HTTP_201_CREATED)
async def create_posts(db: db_dependency, title: str = Form(...), content: str = Form(...), user_id: int = Form(...), images: UploadFile = File()):
    post = PostBase(title = title,
                    content = content,
                    user_id = user_id,
                    images = await handle_image(images))
    db_post = models.Post(**post.dict())
    return db_post
    db.add(db_post)
    db.commit()
    return db_post

@app.get('/posts/', status_code=status.HTTP_200_OK)
async def read_posts(db: db_dependency, id: int | None = None):
    if id is None:
        posts = db.query(models.Post).all()
    else:
        posts = db.query(models.Post).filter(models.Post.id == id).first()
    return posts

@app.put('/posts/{id}', status_code=status.HTTP_200_OK)
async def update_posts(id: int, post_base: PostBase, db: db_dependency):
    posts = db.query(models.Post).filter(models.Post.id == id).first()
    if posts is None:
        return HTTPException(status_code=400, detail='User not found')
    post_data = post_base.dict(exclude_unset=True)
    for key, value in post_data.items():
        setattr(posts, key, value)
    db.add(posts)
    db.commit()
    db.refresh(posts)
    return posts

@app.delete('/posts/{id}', status_code=status.HTTP_200_OK)
async def delete_posts(id: int, db: db_dependency):
    posts = db.query(models.Post).filter(models.Post.id == id).first()
    if posts is None:
        return HTTPException(status_code=400, detail='User not Found')
    db.delete(posts)
    db.commit()
    return posts

@app.post('/users/', status_code=status.HTTP_201_CREATED)
async def create_users(db: db_dependency, users: UserBase):
    db_user = models.User(**users.dict())
    # db.add(db_user)
    # db.commit()
    return db_user

@app.get('/users/', status_code=status.HTTP_200_OK)
async def read_users(db: db_dependency, id: int | None = None):
    if id is None:
        user = db.query(models.User).all()
    else:
        user = db.query(models.User).filter(models.User.id == id).first()
    return user

@app.put('/users/{id}', status_code=status.HTTP_200_OK)
async def update_users(id: int, user_base: UserBase, db: db_dependency):
    user = db.query(models.User).filter(models.User.id == id).first()
    if user is None:
        return HTTPException(status_code=400, detail='User not found')
    user_data = user_base.dict(exclude_unset=True)
    for key, value in user_data.items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.delete('/users/{id}', status_code=status.HTTP_200_OK)
async def delete_user(id: int, db: db_dependency):
    user = db.query(models.User).filter(models.User.id == id).first()
    if user is None:
        return HTTPException(status_code=400, detail='User not Found')
    db.delete(user)
    db.commit()
    return user