from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, Request, Query
from sqladmin import Admin, ModelView
from fastapi.security import OAuth2PasswordBearer
from sqladmin.authentication import AuthenticationBackend
from pydantic import BaseModel, Field, FilePath
from fastapi.staticfiles import StaticFiles
from typing import Annotated
import os
from models import User, Post, FileData, Login
import models
import aiofiles
from database import engine, SessionLocal
from sqlalchemy.orm import Session
from datetime import datetime
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form['username'], form['password']
        db = SessionLocal()
        user = db.query(Login).filter(Login.username == username, Login.password == password).first()
        if user:
            request.session.update({'token': 'aut'})
            return True
        return False
        # return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get('token')
        if not token:
            redirect_uri = request.url_for('login_google')
            return await google.authorize_redirect(request, redirect_uri)
        return True

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

BASEDIR = os.path.dirname(__file__)
app = FastAPI(title="Learning FastAPI App",
    description=description,
    contact={
        "name": "Admin panel link",
        "url": "http://radixusers2.com:8000/admin"
    },openapi_tags = tags_metadata)
app.add_middleware(SessionMiddleware, secret_key="aut")

oauth = OAuth()
oauth.register(
    'google',
    client_id='785824750434-q15pq49a57qtkubne6suukufa4g740sj.apps.googleusercontent.com',
    client_secret='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',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'prompt': 'select_account',
    },
)
google = oauth.create_client('google')


app.mount('/images', StaticFiles(directory="images"), name="images")
authentication_backend = AdminAuth(secret_key="aut")
admin = Admin(app = app, engine = engine, authentication_backend = authentication_backend)
# admin = Admin(app = app, engine = engine)
models.Base.metadata.create_all(bind=engine)

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserAdmin(ModelView, model = User):
    column_list = [User.id, User.username]

class PostAdmin(ModelView, model = Post):
    column_list = [Post.id, Post.title, Post.content, User.username]
    # for i in column_list:
    #     print(i)

admin.add_view(UserAdmin)
admin.add_view(PostAdmin)

@admin.app.route("/auth/google")
async def login_google(request: Request):
    token = await google.authorize_access_token(request)
    user = token.get('userinfo')
    if user:
        request.session['user'] = user
    return RedirectResponse(request.url_for("admin:index"))

@app.post('/posts', status_code=status.HTTP_201_CREATED, tags=['Post'])
async def create_posts(post: PostBase, db: Session=Depends(get_db)):
    db_post = models.Post(**post.dict())
    db.add(db_post)
    return db_post

@app.get('/posts/', status_code=status.HTTP_200_OK, tags=['Post'])
async def read_posts(id: int = 0, db: Session=Depends(get_db)):
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
