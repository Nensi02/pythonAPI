from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, Request, Query
from sqladmin import Admin, ModelView
from typing import Union
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
from starlette.applications import Starlette

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        # form = await request.form()
        # username, password = form['username'], form['password']
        # db = SessionLocal()
        # user = db.query(Login).filter(Login.username == username, Login.password == password).first()
        # if user:app
        #     request.session.update({'token': 'aut'})
        #     return True
        # return False
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Union[bool, RedirectResponse]:
        token = request.session.get('token')
        print('nena')
        print(token)
        print(not token)
        if not token:
            redirect_uri = request.url_for('login_google')
            return await google.authorize_redirect(request, redirect_uri)
            # return False
        return True

BASEDIR = os.path.dirname(__file__)
app = Starlette()
app.add_middleware(SessionMiddleware, secret_key="aut")

oauth = OAuth()
oauth.register(
    'google',
    client_id='514682015979-ivalkcpkp32nb3r10clu3e9tadftnfp6.apps.googleusercontent.com',
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
# admin = Admin(app = app, engine = engine, authentication_backend = authentication_backend)
admin = Admin(app=app, engine=engine, authentication_backend=authentication_backend)
# admin = Admin(app = app, engine = engine)
models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserAdmin(ModelView, model = User):
    column_list = [User.id, User.username]
    form_excluded_columns = [User.user_id]

class PostAdmin(ModelView, model = Post):
    column_list = [Post.id, Post.title, Post.content, Post.username, Post.user_id]
    form_excluded_columns = [Post.id]

admin.add_view(UserAdmin)
admin.add_view(PostAdmin)

@admin.app.route("/auth/google")
async def login_google(request: Request):
    token = await google.authorize_access_token(request)
    user = token.get('userinfo')
    print('nenis')
    print(user)
    if user:
        request.session['token'] = user
    return RedirectResponse(request.url_for("admin:index"))
