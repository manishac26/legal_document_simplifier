# Backend/main.py (with LLM integration and AI4Bharat translation)
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
import random
import traceback
import requests
import json
import time
import os

# Set Tesseract path (update this if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# LLM Configuration - Using Hugging Face Inference API for Mistral-7B
LLM_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
# IMPORTANT: Do NOT hard-code API tokens in source. Set the token in the environment
# variable HF_API_TOKEN (for example: setx HF_API_TOKEN "your_token" on Windows or
# export HF_API_TOKEN=your_token on Linux/macOS). Default is empty string.
LLM_API_TOKEN = os.getenv("HF_API_TOKEN", "")
LLM_TIMEOUT = 30  # seconds

# AI4Bharat Translation API Configuration
AI4BHARAT_TRANSLATION_API = "https://api.ai4bharat.org/translate"

AI4BHARAT_LANGUAGES = {
    "hindi": "hi",
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
    "marathi": "mr",
    "gujarati": "gu",
    "kannada": "kn",
    "malayalam": "ml",
    "punjabi": "pa",
    "odia": "or",
    "assamese": "as",
    "english": "en"
}

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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Risk categories with color codes
RISK_CATEGORIES = {
    "obligation": {"label": "Obligation", "color": "#3B82F6", "class": "obligation"},
    "penalty": {"label": "Penalty", "color": "#EF4444", "class": "penalty"},
    "condition": {"label": "Condition", "color": "#F97316", "class": "condition"},
    "right": {"label": "Right", "color": "#10B981", "class": "right"},
    "definition": {"label": "Definition", "color": "#8B5CF6", "class": "definition"},
}

# Pattern matching for legal terms
RISK_PATTERNS = {
    "obligation": [r"shall\b", r"must\b", r"is required to\b", r"are obligated to\b", r"duty to\b"],
    "penalty": [r"penalty\b", r"fine\b", r"damages\b", r"liable\b", r"indemnify\b", r"breach\b"],
    "condition": [r"if\b", r"unless\b", r"provided that\b", r"subject to\b", r"conditional upon\b"],
    "right": [r"may\b", r"entitled to\b", r"right\b", r"option\b", r"privilege\b"],
    "definition": [r"means\b", r"refers to\b", r"defined as\b", r"hereinafter\b", r"for the purposes of\b"],
}

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

def identify_legal_risks(text: str) -> List[Dict]:
    """Identify legal risks in text using pattern matching"""
    risks = []
    try:
        if not text or not isinstance(text, str):
            return risks
            
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_pos = 0
        for sentence in sentences:
            for category, patterns in RISK_PATTERNS.items():
                for pattern in patterns:
                    try:
                        matches = re.finditer(pattern, sentence, re.IGNORECASE)
                        for match in matches:
                            risks.append({
                                "text": match.group(),
                                "start": current_pos + match.start(),
                                "end": current_pos + match.end(),
                                "category": category,
                                "label": RISK_CATEGORIES[category]["label"],
                                "color": RISK_CATEGORIES[category]["color"],
                                "class": RISK_CATEGORIES[category]["class"],
                                "confidence": round(random.uniform(0.7, 0.95), 2)
                            })
                    except Exception as e:
                        print(f"Error in pattern matching: {e}")
                        continue
            current_pos += len(sentence) + 1
    except Exception as e:
        print(f"Error in identify_legal_risks: {e}")
    
    return risks

def simplify_with_llm(text: str, level: str = "simple") -> str:
    """
    Simplify legal text using Mistral-7B LLM via Hugging Face API
    """
    try:
        if not text or not isinstance(text, str):
            return text
        
        # Truncate very long text to avoid API limits
        if len(text) > 4000:
            text = text[:4000] + "... [text truncated]"
        
        prompt = f"""
        You are a legal expert specializing in simplifying complex legal documents for non-lawyers.
        
        Please simplify the following legal text to make it easy for a layperson to understand.
        Keep the meaning exactly the same but use plain language.
        Break down complex sentences and replace legal jargon with everyday words.
        
        Legal text to simplify:
        {text}
        
        Simplified version:
        """
        
        headers = {
            "Authorization": f"Bearer {LLM_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 1024,
                "temperature": 0.3,
                "do_sample": True,
                "return_full_text": False
            }
        }
        
        response = requests.post(
            LLM_API_URL,
            headers=headers,
            json=payload,
            timeout=LLM_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            simplified_text = result[0]['generated_text'].strip()
            
            # Clean up the response
            simplified_text = re.sub(r'^Simplified version:\s*', '', simplified_text)
            simplified_text = re.sub(r'\n+', '\n', simplified_text).strip()
            
            return simplified_text
        else:
            print(f"LLM API error: {response.status_code} - {response.text}")
            # Fall back to rule-based simplification
            return simplify_text_rule_based(text, level)
            
    except Exception as e:
        print(f"Error in simplify_with_llm: {e}")
        # Fall back to rule-based simplification
        return simplify_text_rule_based(text, level)

def simplify_text_rule_based(text: str, level: str = "simple") -> str:
    """
    Fallback rule-based text simplification
    """
    try:
        if not text or not isinstance(text, str):
            return text
            
        # Basic text cleaning
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Replace complex legal terms with simpler ones
        replacements = {
            "hereinafter": "later in this document",
            "aforementioned": "mentioned before",
            "notwithstanding": "despite",
            "wherein": "where",
            "pursuant to": "according to",
            "hereinafter referred to as": "called",
            "shall": "must",
            "hereby": "by this",
            "herein": "in this",
            "thereof": "of that",
            "therein": "in that",
            "thereto": "to that",
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
            "warrants and represents": "promises and states",
            "force majeure": "unavoidable events",
            "ipso facto": "automatically",
            "inter alia": "among other things",
            "prima facie": "at first glance",
            "pro rata": "proportionally",
            "sine die": "indefinitely",
            "ultra vires": "beyond legal power",
        }
        
        # Apply replacements
        for complex_term, simple_term in replacements.items():
            text = re.sub(r'\b' + complex_term + r'\b', simple_term, text, flags=re.IGNORECASE)
        
        # Break long sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        simplified_sentences = []
        
        for sentence in sentences:
            if len(sentence.split()) > 25:  # Long sentence
                # Simple splitting for demonstration
                parts = re.split(r'[,;:]', sentence)
                if len(parts) > 1:
                    simplified_sentences.extend([p.strip() + '.' for p in parts if p.strip()])
                else:
                    simplified_sentences.append(sentence)
            else:
                simplified_sentences.append(sentence)
        
        return ' '.join(simplified_sentences)
        
    except Exception as e:
        print(f"Error in simplify_text_rule_based: {e}")
        return text

def translate_with_ai4bharat(text: str, target_lang: str = "hindi") -> str:
    """
    Translate text using AI4Bharat translation API (corrected version)
    """
    try:
        if not text or not isinstance(text, str):
            return text
        
        # Get language code
        lang_code = AI4BHARAT_LANGUAGES.get(target_lang.lower(), "hi")
        
        # Prepare the request payload in the correct format for AI4Bharat
        payload = {
            "text": text,
            "source": "en",
            "target": lang_code,
            "domain": "general"  # Added domain parameter
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        print(f"Making request to: {AI4BHARAT_TRANSLATION_API}")
        print(f"Payload: {json.dumps(payload)}")
        
        # Make the API request
        response = requests.post(
            AI4BHARAT_TRANSLATION_API,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"Translation API response status: {response.status_code}")
        print(f"Translation API response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Full API response: {result}")
            
            # Try to extract translated text from different response formats
            translated_text = ""
            
            if "translatedText" in result:
                translated_text = result["translatedText"]
            elif "text" in result:
                translated_text = result["text"]
            elif "output" in result and isinstance(result["output"], list):
                translated_text = result["output"][0] if result["output"] else ""
            elif "translated" in result and isinstance(result["translated"], list):
                translated_text = result["translated"][0] if result["translated"] else ""
            elif isinstance(result, list) and len(result) > 0:
                if "translatedText" in result[0]:
                    translated_text = result[0]["translatedText"]
                elif "text" in result[0]:
                    translated_text = result[0]["text"]
            
            if translated_text:
                print(f"Successfully extracted translation: {translated_text[:100]}...")
                return translated_text
            else:
                print(f"No translation found in response. Full response: {result}")
                return f"[{target_lang.capitalize()} translation format error]"
                
        elif response.status_code == 405:
            print("API endpoint doesn't support POST method, trying GET...")
            # Try GET request as fallback
            return translate_with_ai4bharat_get(text, target_lang)
        else:
            print(f"AI4Bharat API error: {response.status_code} - {response.text}")
            return f"[{target_lang.capitalize()} translation error: HTTP {response.status_code}]"
            
    except Exception as e:
        print(f"Error in translate_with_ai4bharat: {e}")
        traceback.print_exc()
        return f"[{target_lang.capitalize()} translation error: {str(e)}]"

def translate_with_ai4bharat_get(text: str, target_lang: str = "hindi") -> str:
    """
    Alternative GET method for AI4Bharat translation
    """
    try:
        lang_code = AI4BHARAT_LANGUAGES.get(target_lang.lower(), "hi")
        
        params = {
            "text": text,
            "source": "en",
            "target": lang_code
        }
        
        response = requests.get(
            AI4BHARAT_TRANSLATION_API,
            params=params,
            headers={"Accept": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            # Parse response similarly to POST method
            if "translatedText" in result:
                return result["translatedText"]
            return f"[GET method success but format issue]"
        else:
            return f"[GET method failed: HTTP {response.status_code}]"
            
    except Exception as e:
        return f"[GET method error: {str(e)}]"

def get_translation(text: str, target_lang: str = "hindi") -> str:
    """
    Main translation function with multiple fallback options
    """
    # Try AI4Bharat first
    result = translate_with_ai4bharat(text, target_lang)
    
    # If AI4Bharat fails, try other methods
    if result.startswith('[') and 'error' in result.lower():
        print("AI4Bharat failed, trying alternative methods...")
        
        # Try Google Translate (if installed)
        try:
            from googletrans import Translator
            translator = Translator()
            translation = translator.translate(text, dest=target_lang)
            if translation and translation.text:
                return translation.text
        except ImportError:
            print("googletrans not installed")
        except Exception as e:
            print(f"Google Translate failed: {e}")
        
        # Fallback to mock translation
        return get_mock_translation(text, target_lang)
    
    return result

def get_mock_translation(text: str, target_lang: str = "hindi") -> str:
    """
    Comprehensive mock translation with actual Hindi words
    """
    # Common legal terms translations
    legal_terms = {
        "shall": "करेगा",
        "must": "अवश्य",
        "required": "आवश्यक",
        "obligation": "दायित्व",
        "penalty": "जुर्माना",
        "contract": "अनुबंध",
        "agreement": "समझौता",
        "party": "पक्ष",
        "damages": "क्षतिपूर्ति",
        "liable": "उत्तरदायी",
        "indemnify": "क्षतिपूर्ति करना",
        "breach": "उल्लंघन",
        "condition": "शर्त",
        "right": "अधिकार",
        "duty": "कर्तव्य",
        "payment": "भुगतान",
        "termination": "समाप्ति",
        "clause": "धारा",
        "section": "अनुभाग"
    }
    
    # Translate common legal terms
    translated_text = text
    for english, hindi in legal_terms.items():
        translated_text = re.sub(r'\b' + english + r'\b', hindi, translated_text, flags=re.IGNORECASE)
    
    # Add language prefix
    lang_prefixes = {
        "hindi": "[हिंदी अनुवाद] ",
        "bengali": "[বাংলা অনুবাদ] ",
        "tamil": "[தமிழ் மொழிபெயர்ப்பு] ",
        "telugu": "[తెలుగు అనువాదం] ",
        "marathi": "[मराठी भाषांतर] ",
        "gujarati": "[ગુજરાતી અનુવાદ] ",
        "kannada": "[ಕನ್ನಡ ಅನುವಾದ] ",
        "malayalam": "[മലയാളം വിവർത്തനം] ",
        "punjabi": "[ਪੰਜਾਬੀ ਅਨੁਵਾਦ] ",
        "odia": "[ଓଡିଆ ଅନୁବାଦ] ",
        "assamese": "[অসমীয়া অনুবাদ] "
    }
    
    prefix = lang_prefixes.get(target_lang.lower(), f"[{target_lang} translation] ")
    return prefix + translated_text

def add_color_annotations(text: str, risks: List[Dict]) -> str:
    """Add HTML span tags with color coding for risks"""
    if not text or not risks:
        return text or ""
    
    try:
        # Sort risks by start position in reverse order to avoid offset issues
        risks_sorted = sorted(risks, key=lambda x: x['start'], reverse=True)
        
        annotated_text = text
        for risk in risks_sorted:
            try:
                start = risk['start']
                end = risk['end']
                
                # Validate positions
                if start < 0 or end > len(text) or start >= end:
                    continue
                
                risk_text = text[start:end]
                
                span_tag = f'<span style="background-color: {risk["color"]}20; border: 1px solid {risk["color"]}; padding: 2px 4px; border-radius: 3px; margin: 0 2px;" title="{risk["label"]} (Confidence: {risk.get("confidence", 0.8)*100}%)">{risk_text}</span>'
                
                annotated_text = annotated_text[:start] + span_tag + annotated_text[end:]
            except Exception as e:
                print(f"Error adding annotation for risk: {e}")
                continue
        
        return annotated_text
    except Exception as e:
        print(f"Error in add_color_annotations: {e}")
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

# Test endpoint for debugging
@app.get("/test-simplify")
async def test_simplify():
    test_text = "The party shall indemnify and hold harmless the other party from any damages pursuant to the terms herein. Notwithstanding anything to the contrary, the client must pay all fees prior to termination."
    try:
        print("Testing LLM simplification...")
        
        # Simplify text using LLM
        simplified = simplify_with_llm(test_text, "simple")
        print(f"LLM Simplified text: {simplified}")
        
        # Identify risks
        risks = identify_legal_risks(simplified)
        print(f"Found {len(risks)} risks")
        
        # Add color annotations
        annotated = add_color_annotations(simplified, risks)
        print("Annotations added successfully")
        
        return {
            "original": test_text,
            "simplified": simplified,
            "annotated": annotated,
            "risks": risks,
            "risk_count": len(risks),
            "success": True
        }
    except Exception as e:
        error_msg = f"Error in test_simplify: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return {"error": error_msg, "success": False}

# Test endpoint for translation
@app.get("/test-translate")
async def test_translate():
    test_text = "The party shall indemnify and hold harmless the other party from any damages."
    try:
        print("Testing AI4Bharat translation...")
        
        # Translate text using AI4Bharat
        translated = translate_with_ai4bharat(test_text, "hindi")
        print(f"Translated text: {translated}")
        
        return {
            "original": test_text,
            "translated": translated,
            "success": True
        }
    except Exception as e:
        error_msg = f"Error in test_translate: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return {"error": error_msg, "success": False}
    
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
        
        print(f"Simplifying text: {text[:100]}...")
        print(f"Simplification level: {level}")
        
        # Identify risks in original text
        risks = identify_legal_risks(text)
        print(f"Found {len(risks)} risks in original text")
        
        # Simplify text using LLM (with fallback to rule-based)
        simplified = simplify_with_llm(text, level)
        print(f"Simplified text: {simplified[:100]}...")
        
        # Identify risks in simplified text
        simplified_risks = identify_legal_risks(simplified)
        print(f"Found {len(simplified_risks)} risks in simplified text")
        
        # Add color annotations to both texts
        annotated_original = add_color_annotations(text, risks)
        annotated_simplified = add_color_annotations(simplified, simplified_risks)
        
        # Update database with simplified text
        try:
            conn = sqlite3.connect('legal_app.db')
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE documents SET simplified_text = ? WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (simplified, current_user["id"])
            )
            conn.commit()
            conn.close()
        except Exception as db_error:
            print(f"Database update error (non-critical): {db_error}")
        
        return {
            "original_text": text,
            "simplified_text": simplified,
            "original_risks": risks,
            "simplified_risks": simplified_risks,
            "annotated_original": annotated_original,
            "annotated_simplified": annotated_simplified,
            "success": True
        }
    
    except Exception as e:
        print(f"Error in simplify endpoint: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error simplifying text: {str(e)}")

@app.post("/translate")
async def translate(text_data: dict, current_user: dict = Depends(get_current_user)):
    try:
        text = text_data.get("text", "")
        target_lang = text_data.get("language", "hindi")
        
        print(f"Translating text: {text[:100]}...")
        print(f"Target language: {target_lang}")
        
        # Use the enhanced translation function
        translated = get_translation(text, target_lang)
        
        print(f"Final translated text: {translated[:100]}...")
        
        # Identify risks in translated text
        risks = identify_legal_risks(translated)
        print(f"Found {len(risks)} risks in translated text")
        
        # Update database with translated text
        try:
            conn = sqlite3.connect('legal_app.db')
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE documents SET translated_text = ? WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (translated, current_user["id"])
            )
            conn.commit()
            conn.close()
        except Exception as db_error:
            print(f"Database update error (non-critical): {db_error}")
        
        return {
            "original_text": text,
            "translated_text": translated,
            "risks": risks,
            "success": True,
            "translation_service": "ai4bharat" if not translated.startswith('[') else "fallback"
        }
    
    except Exception as e:
        print(f"Error in translate endpoint: {str(e)}")
        traceback.print_exc()
        # Return mock translation even on complete failure
        fallback_translation = get_mock_translation(text_data.get("text", ""), text_data.get("language", "hindi"))
        return {
            "original_text": text_data.get("text", ""),
            "translated_text": fallback_translation,
            "risks": [],
            "success": False,
            "error": str(e),
            "translation_service": "fallback"
        }
@app.get("/check-translation-api")
async def check_translation_api():
    """Check the status of translation APIs"""
    test_text = "Hello world"
    
    # Test different endpoints
    endpoints = [
        "https://api.ai4bharat.org/translate",
        "https://models.ai4bharat.org/translate/a2b",
        "https://translate.ai4bharat.org/translate"
    ]
    
    results = {}
    
    for endpoint in endpoints:
        try:
            global AI4BHARAT_TRANSLATION_API
            AI4BHARAT_TRANSLATION_API = endpoint
            
            response = requests.post(
                endpoint,
                json={"text": test_text, "source": "en", "target": "hi"},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            results[endpoint] = {
                "status": response.status_code,
                "headers": dict(response.headers),
                "response": response.text[:200] if response.text else "No response body"
            }
            
        except Exception as e:
            results[endpoint] = {"error": str(e)}
    
    return {"api_check": results, "test_text": test_text}
@app.get("/languages")
async def get_supported_languages():
    """Get list of supported languages for translation"""
    return {
        "languages": list(AI4BHARAT_LANGUAGES.keys()),
        "language_codes": AI4BHARAT_LANGUAGES
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)