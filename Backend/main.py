# Backend/main.py (complete fixed version)
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import sqlite3
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import io
import re
from typing import Dict, List, Optional
from pydantic import BaseModel

# Set Tesseract path (update this if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Pydantic models for authentication
class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int

# JWT settings
SECRET_KEY = "your-secret-key-here-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

app = FastAPI()

# CORS middleware - updated configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]  # Expose all headers
)

# Explicit OPTIONS handler for CORS preflight requests
@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    return JSONResponse(status_code=200)

# CORS headers middleware
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('legal_app.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create documents table to store user uploads
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        original_text TEXT,
        simplified_text TEXT,
        translated_text TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Risk categories with color codes
RISK_CATEGORIES = {
    "obligation": {"label": "Obligation", "color": "blue", "class": "obligation"},
    "penalty": {"label": "Penalty", "color": "red", "class": "penalty"},
    "condition": {"label": "Condition", "color": "orange", "class": "condition"},
    "right": {"label": "Right", "color": "green", "class": "right"},
    "definition": {"label": "Definition", "color": "purple", "class": "definition"},
}

def identify_legal_risks(text: str) -> List[Dict]:
    """
    Identify legal risks in text using pattern matching
    """
    risks = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Pattern matching for legal terms
    patterns = {
        "obligation": [r"shall", r"must", r"is required to", r"are obligated to", r"duty to"],
        "penalty": [r"penalty", r"fine", r"damages", r"liable", r"indemnify", r"breach"],
        "condition": [r"if", r"unless", r"provided that", r"subject to", r"conditional upon"],
        "right": [r"may", r"entitled to", r"right", r"option", r"privilege"],
        "definition": [r"means", r"refers to", r"defined as", r"hereinafter", r"for the purposes of"]
    }
    
    current_pos = 0
    for sentence in sentences:
        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    risks.append({
                        "text": match.group(),
                        "start": current_pos + match.start(),
                        "end": current_pos + match.end(),
                        "category": category,
                        "label": RISK_CATEGORIES[category]["label"],
                        "color": RISK_CATEGORIES[category]["color"],
                        "class": RISK_CATEGORIES[category]["class"]
                    })
        
        current_pos += len(sentence) + 1  # +1 for the space
    
    return risks

def simplify_text(text: str, level: str = "simple") -> str:
    """
    Simplify legal text based on complexity level using rule-based approach
    """
    # Basic text cleaning
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Replace complex legal terms with simpler ones
    replacements = {
        # Simple level replacements
        "hereinafter": "later in this document",
        "aforementioned": "mentioned before",
        "notwithstanding": "despite",
        "wherein": "where",
        "pursuant to": "according to",
        "hereinafter referred to as": "called",
        "shall": "will",
        "hereby": "by this",
        "herein": "in this",
        "thereof": "of that",
        "therein": "in that",
        "thereto": "to that",
        
        # Moderate level replacements
        "not less than": "at least",
        "not more than": "at most",
        "in the event that": "if",
        "for the purpose of": "to",
        "with respect to": "about",
        "prior to": "before",
        "subsequent to": "after",
        "in accordance with": "by",
        "shall be deemed": "is considered",
        "be liable for": "be responsible for",
        "indemnify and hold harmless": "protect from losses",
        
        # Advanced level replacements
        "notwithstanding anything to the contrary": "even if other parts say differently",
        "force majeure": "unavoidable events",
        "ipso facto": "automatically",
        "inter alia": "among other things",
        "prima facie": "at first glance",
        "bona fide": "in good faith",
    }
    
    # Apply replacements based on simplification level
    for complex_term, simple_term in replacements.items():
        if level == "simple" or level == "moderate" or level == "advanced":
            text = re.sub(r'\b' + complex_term + r'\b', simple_term, text, flags=re.IGNORECASE)
    
    # Additional processing for advanced level
    if level == "advanced":
        # Split long sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        simplified_sentences = []
        
        for sentence in sentences:
            # If sentence is too long, try to split it
            if len(sentence.split()) > 20:
                # Try to split at conjunctions
                parts = re.split(r',\s+(?:and|or|but)\s+', sentence)
                if len(parts) > 1:
                    simplified_sentences.extend(parts)
                else:
                    simplified_sentences.append(sentence)
            else:
                simplified_sentences.append(sentence)
        
        text = '. '.join(simplified_sentences)
    
    return text

# Password utilities
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# User utilities
def get_user_by_email(email: str):
    conn = sqlite3.connect('legal_app.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            "id": user[0],
            "name": user[1],
            "email": user[2],
            "password": user[3]
        }
    return None

def create_user(name: str, email: str, password: str):
    hashed_password = get_password_hash(password)
    conn = sqlite3.connect('legal_app.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, hashed_password)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

# JWT utilities
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    conn = sqlite3.connect('legal_app.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user is None:
        raise credentials_exception
    return {
        "id": user[0],
        "name": user[1],
        "email": user[2]
    }

# Authentication endpoints
@app.post("/signup", response_model=Token)
async def signup(user: UserCreate):
    # Check if user already exists
    existing_user = get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user_id = create_user(user.name, user.email, user.password)
    if not user_id:
        raise HTTPException(status_code=400, detail="Error creating user")
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user_id)}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user_id
    }

@app.post("/login", response_model=Token)
async def login(user: UserLogin):
    # Check if user exists
    db_user = get_user_by_email(user.email)
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(db_user["id"])}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user["id"]
    }

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["id"])}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["id"]
    }

@app.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

@app.get("/")
async def root():
    return {"message": "Welcome to the Legal Document Simplifier API"}

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    try:
        content = await file.read()

        if file.filename.endswith(".pdf"):
            pdf_doc = fitz.open(stream=content, filetype="pdf")
            text = ""
            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]
                text += page.get_text()
                if not text.strip():  # if no text layer, run OCR
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    text += pytesseract.image_to_string(img)
            
            # Store in database
            conn = sqlite3.connect('legal_app.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (user_id, original_text) VALUES (?, ?)",
                (current_user["id"], text)
            )
            conn.commit()
            conn.close()
            
            return {"extracted_text": text.strip()}

        elif file.filename.endswith((".png", ".jpg", ".jpeg")):
            image = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(image)
            
            # Store in database
            conn = sqlite3.connect('legal_app.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (user_id, original_text) VALUES (?, ?)",
                (current_user["id"], text)
            )
            conn.commit()
            conn.close()
            
            return {"extracted_text": text.strip()}

        return {"error": "Unsupported file format"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/simplify")
async def simplify(text_data: dict, current_user: dict = Depends(get_current_user)):
    try:
        text = text_data.get("text", "")
        level = text_data.get("level", "simple")
        
        # Identify risks in original text
        risks = identify_legal_risks(text)
        
        # Simplify text using rule-based approach
        simplified = simplify_text(text, level)
        
        # Identify risks in simplified text
        simplified_risks = identify_legal_risks(simplified)
        
        # Update database with simplified text
        conn = sqlite3.connect('legal_app.db')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE documents SET simplified_text = ? WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (simplified, current_user["id"])
        )
        conn.commit()
        conn.close()
        
        return {
            "original_text": text,
            "simplified_text": simplified,
            "original_risks": risks,
            "simplified_risks": simplified_risks
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error simplifying text: {str(e)}")

@app.post("/translate")
async def translate(text_data: dict, current_user: dict = Depends(get_current_user)):
    try:
        text = text_data.get("text", "")
        target_lang = text_data.get("language", "Hindi")
        
        # For demo purposes, we'll just return the text with a prefix
        # In a real implementation, integrate with a translation API
        translated = f"[{target_lang} translation] {text}"
        
        # Identify risks in translated text
        risks = identify_legal_risks(translated)
        
        # Update database with translated text
        conn = sqlite3.connect('legal_app.db')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE documents SET translated_text = ? WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (translated, current_user["id"])
        )
        conn.commit()
        conn.close()
        
        return {
            "translated_text": translated,
            "risks": risks
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error translating text: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)