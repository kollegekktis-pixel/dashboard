import os
import secrets
from datetime import datetime
from typing import Optional
from pathlib import Path

import bcrypt
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Cookie, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# ===========================
# SETUP ПАПОК
# ===========================
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.xlsx'}

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
    subject = Column(String)  # Предмет
    category = Column(String)  # Категория учителя
    experience = Column(Integer, default=0)  # Стаж работы
    
    achievements = relationship("Achievement", back_populates="user")

    def check_password(self, password: str) -> bool:
        password_bytes = password.encode('utf-8')[:72]
        return bcrypt.checkpw(password_bytes, self.password_hash.encode('utf-8'))


class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    achievement_type = Column(String, default="student")  # student, teacher, social, educational
    student_name = Column(String, nullable=True)  # ФИО ученика
    place = Column(String)  # 1, 2, 3, certificate
    
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String)
    level = Column(String)
    file_path = Column(String, nullable=True)  # ✅ ВАЖНО: путь относительно UPLOAD_DIR
    file_name = Column(String, nullable=True)  # ✅ Оригинальное имя файла
    points = Column(Float, default=0.0)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="achievements")


Base.metadata.create_all(bind=engine)

# ===========================
# PASSWORD HASHING
# ===========================
def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


# ===========================
# FILE UTILITIES
# ===========================
def validate_file(filename: str) -> bool:
    """Проверка расширения файла"""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


async def save_upload_file(file: UploadFile, user_id: int) -> tuple[str, str]:
    """Сохраняет файл и возвращает (relative_path, original_name)"""
    if not validate_file(file.filename):
        raise ValueError(f"Недопустимый формат файла. Разрешено: {', '.join(ALLOWED_EXTENSIONS)}")
    
    # Читаем файл в память
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5 МБ
        raise ValueError("Файл слишком большой (макс. 5 МБ)")
    
    # Генерируем уникальное имя
    import uuid
    file_ext = Path(file.filename).suffix.lower()
    unique_name = f"{user_id}_{uuid.uuid4()}{file_ext}"
    
    # Сохраняем на диск
    file_path = UPLOAD_DIR / unique_name
    with open(file_path, "wb") as f:
        f.write(content)
    
    return unique_name, file.filename


# ===========================
# APP SETUP
# ===========================
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
serializer = URLSafeTimedSerializer(SECRET_KEY)

ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true").lower() == "true"

# ===========================
# TRANSLATIONS (сокращено для примера)
# ===========================
TRANSLATIONS = {
    "ru": {
        "app_title": "Jetistik Hub",
        "dashboard": "Панель",
        "profile": "Профиль",
        "my_achievements": "Мои достижения",
        "admin_panel": "Админ-панель",
        "reports": "Отчёты",
        "welcome_user": "Добро пожаловать",
        "total_points": "Всего баллов",
        "pending_achievements": "Ожидают проверки",
        "approved_achievements": "Подтверждено",
        "student_achievements": "Достижения ученика",
        "teacher_achievements": "Достижения педагога",
        "social_activity": "Общественно-социальная активность",
        "educational_activity": "Воспитательная активность",
        "category_competitions": "Конкурсы",
        "category_olympiads": "Олимпиады",
        "category_projects": "Проекты",
        "category_experience_exchange": "Обмен опыта",
        "category_methodical": "Методические пособия",
        "level_city": "Городской",
        "level_regional": "Областной",
        "level_national": "Республиканский",
        "level_international": "Международный",
        "place_1": "1 место",
        "place_2": "2 место",
        "place_3": "3 место",
        "place_certificate": "Сертификат участника",
        "status_pending": "Ожидает",
        "status_approved": "Подтверждено",
        "status_rejected": "Отклонено",
        "success": "Успешно!",
        "error": "Ошибка!",
    },
    "kk": {
        "app_title": "Jetistik Hub",
        "dashboard": "Басты бет",
        "profile": "Профиль",
        "my_achievements": "Менің жетістіктерім",
        "admin_panel": "Әкімші панелі",
        "reports": "Есептер",
        "welcome_user": "Қош келдіңіз",
        "total_points": "Барлық ұпайлар",
        "pending_achievements": "Тексеруді күтуде",
        "approved_achievements": "Расталған",
        "student_achievements": "Оқушының жетістіктері",
        "teacher_achievements": "Педагогтың жетістіктері",
        "social_activity": "Қоғамдық-әлеуметтік белсенділік",
        "educational_activity": "Тәрбиелік белсенділік",
        "category_competitions": "Конкурстар",
        "category_olympiads": "Олимпиадалар",
        "category_projects": "Жобалар",
        "category_experience_exchange": "Тәжірибе алмасу",
        "category_methodical": "Әдістемелік құралдар",
        "level_city": "Қалалық",
        "level_regional": "Облыстық",
        "level_national": "Республикалық",
        "level_international": "Халықаралық",
        "place_1": "1 орын",
        "place_2": "2 орын",
        "place_3": "3 орын",
        "place_certificate": "Қатысушы сертификаты",
        "status_pending": "Күтуде",
        "status_approved": "Расталған",
        "status_rejected": "Қабылданбаған",
    }
}

def get_translation(lang: str, key: str) -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get(key, key)

# ===========================
# DEPENDENCIES
# ===========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> Optional[User]:
    if not session_token:
        return None
    try:
        user_id = serializer.loads(session_token, max_age=3600 * 24 * 7)
        return db.query(User).filter(User.id == user_id).first()
    except:
        return None


def get_language(language: Optional[str] = Cookie(None)) -> str:
    return language if language in ["ru", "kk"] else "ru"


# ===========================
# STARTUP
# ===========================
@app.on_event("startup")
def create_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin_pass = os.getenv("ADMIN_PASS", "adminpass123")
            hashed_pw = hash_password(admin_pass)
            new_admin = User(
                username="admin",
                password_hash=hashed_pw,
                full_name="Administrator",
                is_admin=True,
                school="System"
            )
            db.add(new_admin)
            db.commit()
            print("✅ Created admin user: admin")
    except Exception as e:
        print(f"⚠️ Error: {e}")
        db.rollback()
    finally:
        db.close()


# ===========================
# ROUTES - Language
# ===========================
@app.get("/set-language/{lang}")
def set_language(lang: str, request: Request):
    if lang not in ["ru", "kk"]:
        lang = "ru"
    response = RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)
    response.set_cookie(key="language", value=lang, max_age=3600 * 24 * 365)
    return response


# ===========================
# ROUTES - AUTH (сокращено)
# ===========================
@app.get("/", response_class=HTMLResponse)
def index(user: User = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, lang: str = Depends(get_language)):
    return templates.TemplateResponse("login.html", {"request": request, "lang": lang})


@app.post("/login")
def login_post(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.check_password(password):
        return RedirectResponse(url="/login?error=invalid", status_code=303)
    
    token = serializer.dumps(user.id)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=3600 * 24 * 7)
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response


# ===========================
# ROUTES - DASHBOARD
# ===========================
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request,
              user: User = Depends(get_current_user),
              db: Session = Depends(get_db),
              lang: str = Depends(get_language)):
    if not user:
        return RedirectResponse(url="/login")

    t = lambda key: get_translation(lang, key)
    achievements = db.query(Achievement).filter(Achievement.user_id == user.id).all()
    all_users = db.query(User).all() if user.is_admin else []
    pending_achievements = db.query(Achievement).filter(Achievement.status == "pending").all() if user.is_admin else []

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "achievements": achievements,
        "all_users": all_users,
        "pending_achievements": pending_achievements,
        "lang": lang,
        "t": t
    })


# ===========================
# ROUTES - ADD ACHIEVEMENT ✅ ИСПРАВЛЕНО
# ===========================
@app.post("/add-achievement")
async def add_achievement(
    achievement_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(...),
    level: str = Form(...),
    place: str = Form(...),
    student_name: str = Form(None),
    file: Optional[UploadFile] = File(None),
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
    calculated_points = points_table.get(level, {}).get(place, 0)
    
    file_path = None
    file_name = None
    
    # ✅ Обработка файла
    if file and file.filename:
        try:
            file_path, file_name = await save_upload_file(file, user.id)
        except ValueError as e:
            # Возвращаем ошибку
            return RedirectResponse(url=f"/dashboard?error={str(e)}", status_code=303)
    
    # Создаём достижение
    new_achievement = Achievement(
        user_id=user.id,
        achievement_type=achievement_type,
        student_name=student_name,
        title=title,
        description=description,
        category=category,
        level=level,
        place=place,
        file_path=file_path,  # ✅ Относительный путь
        file_name=file_name,  # ✅ Оригинальное имя
        points=calculated_points,
        status="pending"
    )
    
    db.add(new_achievement)
    db.commit()
    
    return RedirectResponse(url="/dashboard?success=true", status_code=303)


# ===========================
# ROUTES - DOWNLOAD FILE ✅ НОВОЕ
# ===========================
@app.get("/download/{achievement_id}")
def download_file(achievement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Скачивание файла достижения"""
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    
    if not achievement:
        raise HTTPException(status_code=404, detail="Достижение не найдено")
    
    # Проверка прав доступа (только владелец или админ)
    if achievement.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    if not achievement.file_path:
        raise HTTPException(status_code=404, detail="Файл не загружен")
    
    file_full_path = UPLOAD_DIR / achievement.file_path
    
    if not file_full_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден на диске")
    
    return FileResponse(
        path=file_full_path,
        filename=achievement.file_name or "download",
        media_type="application/octet-stream"
    )


# ===========================
# ROUTES - ADMIN ACTIONS
# ===========================
@app.post("/achievement/{achievement_id}/approve")
def approve_achievement(achievement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if achievement:
        achievement.status = "approved"
        db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/achievement/{achievement_id}/reject")
def reject_achievement(achievement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if achievement:
        achievement.status = "rejected"
        db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/achievement/{achievement_id}/delete")
def delete_achievement(achievement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    
    if achievement and (achievement.user_id == user.id or user.is_admin):
        # Удаляем файл с диска
        if achievement.file_path:
            file_path = UPLOAD_DIR / achievement.file_path
            if file_path.exists():
                file_path.unlink()
        
        db.delete(achievement)
        db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/create-user")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    school: str = Form(""),
    subject: str = Form(""),
    category: str = Form(""),
    experience: int = Form(0),
    is_admin: bool = Form(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
    
    if db.query(User).filter(User.username == username).first():
        return RedirectResponse(url="/dashboard?error=username_exists", status_code=303)
    
    hashed_pw = hash_password(password)
    new_user = User(
        username=username,
        password_hash=hashed_pw,
        full_name=full_name,
        school=school,
        subject=subject,
        category=category,
        experience=experience,
        is_admin=is_admin
    )
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/dashboard?success=user_created", status_code=303)
