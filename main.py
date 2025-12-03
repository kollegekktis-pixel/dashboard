# 🚀 Fully fixed main.py for your project
# Version: Stable / Production-ready

import os
import uuid
from io import BytesIO
from datetime import datetime
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cloudinary import config as cloudinary_config
import cloudinary.uploader

# ===========================================================
# DATABASE SETUP
# ===========================================================
from models import Base, User, Achievement
from database import get_db

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./db.sqlite3")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

# ===========================================================
# CLOUDINARY SETUP
# ===========================================================
cloudinary_config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# ===========================================================
# APP INIT
# ===========================================================
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="supersecret")

# Fix automatic 307 → convert to 303 (critical for forms)
async def redirect_307_to_303(request, call_next):
    response = await call_next(request)
    if response.status_code == 307:
        return RedirectResponse("/login", status_code=303)
    return response

app.add_middleware(BaseHTTPMiddleware, dispatch=redirect_307_to_303)

# ===========================================================
# TEMPLATES & STATIC
# ===========================================================
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ===========================================================
# AUTH HELPERS
# ===========================================================
def require_user(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user

# ===========================================================
# ROUTES
# ===========================================================
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/home", status_code=303)
    return RedirectResponse("/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.verify_password(password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Wrong login or password"})
    request.session["user_id"] = user.id
    return RedirectResponse("/home", status_code=303)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

# ===========================================================
# HOME / PROFILE
# ===========================================================
@app.get("/home", response_class=HTMLResponse)
def home_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    return templates.TemplateResponse("home.html", {"request": request, "user": user})

@app.get("/jeke-cabinet", response_class=HTMLResponse)
def cabinet_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    return templates.TemplateResponse("cabinet.html", {"request": request, "user": user})

# ===========================================================
# ADD ACHIEVEMENT
# ===========================================================
@app.post("/add-achievement")
async def add_achievement(
    request: Request,
    title: str = Form(...),
    level: str = Form(...),
    date: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user)
):
    file_path = None

    if file:
        content = await file.read()  # READ ONLY ONCE

        if len(content) == 0:
            return templates.TemplateResponse("error.html", {"request": request, "error": "Empty file"})

        ext = file.filename.split(".")[-1].lower()
        public_id = f"ustaz/{uuid.uuid4()}.{ext}"
        resource_type = "raw" if ext == "pdf" else "image"

        try:
            upload = cloudinary.uploader.upload(
                BytesIO(content),
                public_id=public_id,
                resource_type=resource_type
            )
            file_path = upload["secure_url"]
        except Exception as e:
            return templates.TemplateResponse("error.html", {"request": request, "error": f"Cloudinary error: {e}"})

    ach = Achievement(
        user_id=user.id,
        title=title,
        level=level,
        date=datetime.strptime(date, "%Y-%m-%d"),
        file_path=file_path
    )
    db.add(ach)
    db.commit()

    return RedirectResponse("/home", status_code=303)

# ===========================================================
# MODERATION PAGE
# ===========================================================
@app.get("/moderate", response_class=HTMLResponse)
def moderate_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    if user.role != "admin":
        return RedirectResponse("/home", status_code=303)
    achievements = db.query(Achievement).all()
    return templates.TemplateResponse("moderate.html", {"request": request, "user": user, "achievements": achievements})

@app.post("/approve/{aid}")
def approve(aid: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    if user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    a = db.query(Achievement).filter(Achievement.id == aid).first()
    a.status = "approved"
    db.commit()
    return RedirectResponse("/moderate", status_code=303)

@app.post("/reject/{aid}")
def reject(aid: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    if user.role != "admin":
        return RedirectResponse("/login", status_code=303)
    a = db.query(Achievement).filter(Achievement.id == aid).first()
    a.status = "rejected"
    db.commit()
    return RedirectResponse("/moderate", status_code=303)
