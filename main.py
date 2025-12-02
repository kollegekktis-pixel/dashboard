import os
import secrets
from datetime import datetime
from typing import Optional

import bcrypt
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Cookie, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# ===========================
# DATABASE SETUP
# ===========================
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./db.sqlite3"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ===========================
# MODELS
# ===========================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    is_admin = Column(Boolean, default=False)
    school = Column(String)
    subject = Column(String)
    category = Column(String)
    experience = Column(Integer, default=0)
    
    achievements = relationship("Achievement", back_populates="user", cascade="all, delete-orphan")

    def check_password(self, password: str) -> bool:
        password_bytes = password.encode('utf-8')[:72]
        return bcrypt.checkpw(password_bytes, self.password_hash.encode('utf-8'))


class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    achievement_type = Column(String)
    student_name = Column(String)
    title = Column(String)
    description = Column(String)
    category = Column(String)
    level = Column(String)
    place = Column(String)
    file_path = Column(String)
    points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="achievements")


# Create tables
Base.metadata.create_all(bind=engine)

# ===========================
# APP SETUP
# ===========================
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ===========================
# CLOUDINARY SETUP
# ===========================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
serializer = URLSafeTimedSerializer(SECRET_KEY)

ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true").lower() == "true"

# ===========================
# TRANSLATIONS
# ===========================
TRANSLATIONS = {
    "ru": {
        # Общее
        "app_title": "Jetistik Hub",
        "app_subtitle": "Дата-рейтинговая система достижений учителей",
        "language": "Язык",
        "login": "Войти",
        "logout": "Выйти",
        "register": "Регистрация",
        "home": "Главная",
        "profile": "Профиль",
        
        # Главное меню
        "main_page": "Главная Страница",
        "jeke_cabinet": "Jeke Cabinet",
        "jetistik_alany": "Jetistik Alany",
        "rulebox": "RuleBox",
        "ai_tools": "AI Tools",
        
        # Админ
        "admin_panel": "Панель управления",
        "reports": "Отчёты",
        
        # Категории для Qogam Serpin
        "category_social_events": "Социальные мероприятия",
        "category_volunteering": "Волонтёрство",
        "category_community_work": "Общественная работа",
        "category_methodical_leader": "Методист-наставник",
        
        # Категории для Tarbie Arnasy
        "category_educational_events": "Воспитательные мероприятия",
        "category_class_work": "Классная работа",
        "category_parent_work": "Работа с родителями",
        "category_class_management": "Управление классом",
        "category_parent_voice": "Голос родителей",
        "category_specialist_cooperation": "Сотрудничество со специалистами",
        "parent_participation": "Участие родителей",
        "participation_up_to_40": "Участие до 40%",
        "participation_up_to_70": "Участие до 70%",
        "participation_up_to_90": "Участие до 90%",
        
        # Уровни
        "level_school": "Школьный",
        "level_city": "Городской",
        "level_regional": "Областной",
        "level_national": "Республиканский",
        "level_international": "Международный",
        
        # Сообщения
        "error_invalid_credentials": "Неверный логин или пароль",
        "error_username_exists": "Логин уже занят",
        "error_passwords_dont_match": "Пароли не совпадают",
        "success_achievement_added": "Достижение успешно добавлено",
    },
    "kk": {
        # Жалпы
        "app_title": "Jetistik Hub",
        "app_subtitle": "Мұғалім жетістіктерінің деректі-рейтингтік жүйесі",
        "language": "Тіл",
        "login": "Кіру",
        "logout": "Шығу",
        "register": "Тіркелу",
        "home": "Басты бет",
        "profile": "Профиль",
        
        # Басты мәзір
        "main_page": "Басты Бет",
        "jeke_cabinet": "Jeke Cabinet",
        "jetistik_alany": "Jetistik Alany",
        "rulebox": "RuleBox",
        "ai_tools": "AI Tools",
        
        # Әкімші
        "admin_panel": "Басқару панелі",
        "reports": "Есептер",
        
        # Qogam Serpin санаттары
        "category_social_events": "Әлеуметтік іс-шаралар",
        "category_volunteering": "Волонтерлық",
        "category_community_work": "Қоғамдық жұмыс",
        "category_methodical_leader": "Әдіскер-жетекші",
        
        # Tarbie Arnasy санаттары
        "category_educational_events": "Тәрбиелік іс-шаралар",
        "category_class_work": "Сынып жұмысы",
        "category_parent_work": "Ата-аналармен жұмыс",
        "category_class_management": "Сыныпты басқару",
        "category_parent_voice": "Ата-ананың дауысы",
        "category_specialist_cooperation": "Мамандармен ынтымақтастық",
        "parent_participation": "Ата-ананың қатысуы",
        "participation_up_to_40": "40% дейін қатысу",
        "participation_up_to_70": "70% дейін қатысу",
        "participation_up_to_90": "90% дейін қатысу",
        
        # Деңгейлер
        "level_school": "Мектептік",
        "level_city": "Қалалық",
        "level_regional": "Облыстық",
        "level_national": "Республикалық",
        "level_international": "Халықаралық",
        
        # Хабарламалар
        "error_invalid_credentials": "Логин немесе құпия сөз қате",
        "error_username_exists": "Логин бос емес",
        "error_passwords_dont_match": "Құпия сөздер сәйкес келмейді",
        "success_achievement_added": "Жетістік сәтті қосылды",
    }
}

def get_translation(lang: str, key: str) -> str:
    return TRANSLATIONS.get(lang, {}).get(key, key)

# ===========================
# DEPENDENCY
# ===========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_language(lang: str = Cookie(None)) -> str:
    return lang if lang in ["ru", "kk"] else "kk"

def get_current_user(token: str = Cookie(None), db: Session = Depends(get_db)):
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=86400 * 30)
        user_id = data.get("user_id")
        return db.query(User).filter(User.id == user_id).first()
    except:
        return None

# ===========================
# ROUTES
# ===========================

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/login")

@app.get("/set-language/{lang}")
def set_language(lang: str):
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(key="lang", value=lang, max_age=86400 * 365)
    return response

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, lang: str = Depends(get_language)):
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "lang": lang,
        "t": t,
        "allow_registration": ALLOW_REGISTRATION
    })

@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not user.check_password(password):
        return RedirectResponse(url="/login?error=invalid_credentials", status_code=303)
    
    token = serializer.dumps({"user_id": user.id})
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(key="token", value=token, httponly=True, max_age=86400 * 30)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("token")
    return response

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, lang: str = Depends(get_language)):
    if not ALLOW_REGISTRATION:
        return RedirectResponse(url="/login")
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "lang": lang,
        "t": t
    })

@app.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(...),
    school: str = Form(None),
    db: Session = Depends(get_db)
):
    if not ALLOW_REGISTRATION:
        return RedirectResponse(url="/login")
    
    if password != confirm_password:
        return RedirectResponse(url="/register?error=passwords_dont_match", status_code=303)
    
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return RedirectResponse(url="/register?error=username_exists", status_code=303)
    
    password_bytes = password.encode('utf-8')[:72]
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
    
    new_user = User(
        username=username,
        password_hash=password_hash,
        full_name=full_name,
        school=school,
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/login?success=registered", status_code=303)

@app.get("/home", response_class=HTMLResponse)
def home_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })

@app.get("/admin", response_class=HTMLResponse)
def admin_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Access forbidden")
    
    all_users = db.query(User).all()
    t = lambda key: get_translation(lang, key)
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "all_users": all_users,
        "lang": lang,
        "t": t
    })

@app.post("/add-achievement")
async def add_achievement(
    achievement_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    category: str = Form(...),
    level: str = Form(None),
    place: str = Form(None),
    student_name: str = Form(None),
    file: Optional[UploadFile] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    # Расчёт баллов
    points_table = {
        'city': {'1': 35, '2': 30, '3': 25, 'certificate': 10},
        'regional': {'1': 40, '2': 35, '3': 30, 'certificate': 15},
        'national': {'1': 45, '2': 40, '3': 35, 'certificate': 20},
        'international': {'1': 50, '2': 45, '3': 40, 'certificate': 25}
    }
    
    calculated_points = 0
    if level and place:
        calculated_points = points_table.get(level, {}).get(place, 0)
    
    file_path = None
    if file and file.filename:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            t = lambda key: get_translation(lang, key)
            return RedirectResponse(url=f"/{achievement_type}?error=file_too_large", status_code=303)
        
        import uuid
        file_ext = file.filename.split(".")[-1]
        
        # Попытаться загрузить в Cloudinary
        try:
            public_id = f"jetistik_hub/{uuid.uuid4()}"
            
            upload_result = cloudinary.uploader.upload(
                content,
                public_id=public_id,
                resource_type="auto"
            )
            
            file_path = upload_result['secure_url']
            print(f"✅ File uploaded to Cloudinary: {file_path}")
            
        except Exception as e:
            print(f"⚠️ Cloudinary upload error: {e}")
            # Fallback: сохранить локально
            unique_filename = f"{uuid.uuid4()}.{file_ext}"
            local_path = os.path.join(UPLOAD_DIR, unique_filename)
            
            with open(local_path, "wb") as f:
                f.write(content)
            
            file_path = f"/uploads/{unique_filename}"
            print(f"📁 File saved locally (fallback): {file_path}")
    
    new_achievement = Achievement(
        user_id=user.id,
        achievement_type=achievement_type,
        student_name=student_name,
        title=title,
        description=description,
        category=category,
        level=level,
        place=place,
        file_path=file_path,
        points=calculated_points
    )
    db.add(new_achievement)
    db.commit()
    
    return RedirectResponse(url=f"/{achievement_type.replace('_', '-')}?success=added", status_code=303)

@app.get("/jeke-cabinet", response_class=HTMLResponse)
def jeke_cabinet(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("jeke_cabinet.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })

@app.post("/achievement/{achievement_id}/delete")
def delete_achievement(
    achievement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        return RedirectResponse(url="/login")
    
    achievement = db.query(Achievement).filter(
        Achievement.id == achievement_id,
        Achievement.user_id == user.id
    ).first()
    
    if achievement:
        db.delete(achievement)
        db.commit()
    
    return RedirectResponse(url="/jeke-cabinet", status_code=303)

# ===========================
# JETISTIK ALANY PAGES
# ===========================

@app.get("/jetistik-alany", response_class=HTMLResponse)
def jetistik_alany(
    request: Request,
    user: User = Depends(get_current_user),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("jetistik_alany.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })

@app.get("/oqushy-status", response_class=HTMLResponse)
def oqushy_status(
    request: Request,
    user: User = Depends(get_current_user),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("oqushy_status.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })

@app.get("/sapa-qorzhyn", response_class=HTMLResponse)
def sapa_qorzhyn(
    request: Request,
    user: User = Depends(get_current_user),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("sapa_qorzhyn.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })

@app.get("/qogam-serpin", response_class=HTMLResponse)
def qogam_serpin(
    request: Request,
    user: User = Depends(get_current_user),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("qogam_serpin.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })

@app.get("/tarbie-arnasy", response_class=HTMLResponse)
def tarbie_arnasy(
    request: Request,
    user: User = Depends(get_current_user),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("tarbie_arnasy.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
