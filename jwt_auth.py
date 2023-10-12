from datetime import datetime, timedelta
from typing import Annotated
import os

from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, FilePath
import models
from models import Post, User, FileData, Login
import aiofiles
from database import engine, SessionLocal
from sqlalchemy.orm import Session

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "835ce16d6f2b456dce7b2b3e0dc4fef97c524d2ffbd2b784ee98d2b5b38e9d8d"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10

fake_users_db = {
    "nen": {
        "username": "nen",
        "full_name": "nen",
        "email": "johndoe@example.com",
        "hashed_password": "nen",
        "disabled": False,
    }
}

tags_metadata = [
    {
        "name": "Upload File",
        "description": "Operation with the **Upload files**.",
    },
    {
        "name": "Post",
        "description": "Operation with **post**.",
        "externalDocs": {
            "description": "Post external admin panel",
            "url": "http://radixusers2.com:8000/admin/post/list",
        },
    },
    {
        "name": "User",
        "description": "Operation with **user**.",
        "externalDocs": {
            "description": "User external admin panel",
            "url": "http://radixusers2.com:8000/admin/user/list",
        },
    }
]

description = """
Learning API helps you to practice the API. 🚀

## APIs

* **Users**.
* **Posts**.
* **Upload files**.
"""

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

BASEDIR = os.path.dirname(__file__)
app = FastAPI(title="Learning FastAPI App",
    description=description,
    contact={
        "name": "Admin panel link",
        "url": "http://radixusers2.com:8000/admin"
    },openapi_tags = tags_metadata)

models.Base.metadata.create_all(bind=engine)
app.mount('/images', StaticFiles(directory="images"), name="images")

# Pydantic models
class PostBase(BaseModel):
    title: str = Field(min_length = 5, max_length = 20)
    content: str = Field(min_length = 2, max_length = 20)
    user_id: int = Field(gt = 0)

class UserBase(BaseModel):
    username: str = Field(min_length = 2, max_length = 20)

class Upload(BaseModel):
    filename: str
    filesize: int
    filetype: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    for user_data in db:
        if username == user_data.username:
            user_dict = {'username': user_data.username, 'hashed_password': user_data.password}
            return UserInDB(**user_dict)

def authenticate_user(db: get_db, username: str, password: str):
    users_db = db.query(models.Login).all()
    user = get_user(users_db, username)
    if not user:
        return False
    if password != user.hashed_password:
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Handle image on uploading images
async def handle_image(image: UploadFile, time_value) -> str:
    directory = os.path.join(BASEDIR, 'images/')
    if not os.path.exists(directory):
        os.makedirs(directory)
    contentData = await image.read()
    if image.content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=406, detail="Only .jpeg or .png  files allowed")
    elif image.size > 2000000:
        raise HTTPException(status_code=406, detail = 'Image size must be less than 2 MB')
    filename = image.filename.replace(' ', '_')
    name, ext = os.path.splitext(filename)
    filename = '{0}{1}'.format(time_value, ext)
    async with aiofiles.open(os.path.join(directory, filename), mode = 'wb') as file:
        await file.write(contentData)
    return True

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session=Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    fake_users_db = db.query(models.User).all()
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

# get active user
async def get_current_active_user(
    current_user: Annotated[Login, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session=Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post('/posts', status_code=status.HTTP_201_CREATED, tags=['Post'])
async def create_posts(post: PostBase, db: Session=Depends(get_db)):
    db_post = models.Post(**post.dict())
    db.add(db_post)
    return db_post

@app.get('/posts/', status_code=status.HTTP_200_OK, tags=['Post'], )
async def read_posts(current_user: Annotated[Login, Depends(get_current_active_user)], id: int = 0, db: Session=Depends(get_db)):
    final = []
    if id == 0:
        posts = db.query(Post, User).join(User, User.id == Post.user_id).all()
    else:
        posts = db.query(Post, User).join(User, User.id == Post.user_id).filter(Post.id == id).all()
    if posts is None:
        return HTTPException(status_code = 400, detail = 'Posts Not Found')

    for post, user in posts:
        final.append({
            'id' : post.id,
            'title': post.title,
            'content': post.content,
            'username': user.username
        })
    return final

@app.put('/posts/{id}', status_code=status.HTTP_200_OK, tags=['Post'])
async def update_posts(id: int, post_data_base: PostBase, db: Session=Depends(get_db)):
    posts = db.query(models.Post).filter(models.Post.id == id).first()
    if posts is None:
        return HTTPException(status_code = 400, detail = 'Posts not Found')
    post_data = post_data_base.dict(exclude_unset=True)
    for key, value in post_data.items():
        setattr(posts, key, value)
    db.add(posts)
    db.commit()
    db.refresh(posts)
    return posts

@app.delete('/posts/{id}', status_code=status.HTTP_200_OK, tags=['Post'])
async def delete_post(id: int, db: Session=Depends(get_db)):
    posts = db.query(models.Post).filter(models.Post.id == id).first()
    if posts is None:
        return HTTPException(status_code = 400, detail = 'Posts Not Found')
    db.delete(posts)
    db.commit()
    return {'message': 'delete data'}

@app.post('/users', status_code=status.HTTP_201_CREATED, tags=['User'])
async def create_users(user: UserBase, db: Session=Depends(get_db)):
    db_user = models.User(**user.dict())
    db.add(db_user)
    db.commit()
    return db_user

@app.get('/users/', status_code=status.HTTP_200_OK, tags=['User'])
async def read_user(id: int = 0, db: Session=Depends(get_db)):
    if id == 0:
        user = db.query(models.User).all()
    else:
        user = db.query(models.User).filter(models.User.id == id).first()  
    if user is None:
        return HTTPException(status_code = 400, detail = 'User Not Found')
    return user

@app.put('/users/{id}', status_code=status.HTTP_200_OK, tags=['User'])
async def update_user(id: int, userUpdate: UserBase, db: Session=Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == id).first()
    if user is None:
        return HTTPException(status_code = 400, detail = 'User Not Found')
    user_data = userUpdate.dict(exclude_unset=True)
    setattr(user, 'id', id)
    for key, value in user_data.items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.delete('/users/{id}', status_code=status.HTTP_200_OK, tags=['User'])
async def delete_user(id: int, db: Session=Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == id).first()
    if user is None:
        return HTTPException(status_code = 400, detail = "user not Found")
    db.delete(user)
    db.commit()
    return {'message': 'delete data'}

@app.post("/uploadfile", status_code=status.HTTP_201_CREATED, tags=['Upload File'])
async def create_upload_file(images: UploadFile, db: Session=Depends(get_db)):
    time_value = int(datetime.timestamp(datetime.now()))
    flag = await handle_image(images, time_value)
    if flag is True:
        name, ext = os.path.splitext(images.filename)
        nameValue = '{0}{1}'.format(time_value, ext)
        image_data = Upload(
            filename = nameValue,
            filesize = images.size,
            filetype = ext[1:]
        )
        db_file = models.FileData(**image_data.dict())
        db.add(db_file)
        db.commit()
        return image_data

@app.get('/uploadfile/', status_code=status.HTTP_200_OK, tags=['Upload File'])
async def read_user(request: Request, id: Annotated[int, Query(description = 'Enter Id to get that Data')] = 0, db: Session=Depends(get_db)):
    url = request.url._url
    if id == 0:
        fileData = db.query(models.FileData).all()
        for image_data in fileData:
            image_data.filename = url[:url.index(request.url.path)] + '/images/' + image_data.filename
    else:
        fileData = db.query(models.FileData).filter(models.FileData.id == id).first()
        fileData.filename = url[:url.index(request.url.path)] + '/images/' + fileData.filename
    if fileData is None:
        return HTTPException(status_code = 400, detail = 'Image Data Not Found')
    return fileData

@app.delete('/uploadfile/{id}', status_code=status.HTTP_200_OK, tags=['Upload File'])
async def delete_post(id: int, db: Session=Depends(get_db)):
    image_data = db.query(models.FileData).filter(models.FileData.id == id).first()
    if image_data is None:
        return HTTPException(status_code = 400, detail = 'Image Data Not Found')
    db.delete(image_data)
    os.unlink(os.path.join(BASEDIR, 'images/' + image_data.filename))
    db.commit()
    return {'message': 'delete data'}
