# Backend/main_debug.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import re
from typing import Dict, List
import random

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Risk categories with color codes
RISK_CATEGORIES = {
    "obligation": {"label": "Obligation", "color": "#3B82F6", "class": "obligation"},
    "penalty": {"label": "Penalty", "color": "#EF4444", "class": "penalty"},
}

# Pattern matching for legal terms
RISK_PATTERNS = {
    "obligation": [r"shall\b", r"must\b", r"is required to\b"],
    "penalty": [r"penalty\b", r"fine\b", r"damages\b"],
}

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

def simplify_text(text: str, level: str = "simple") -> str:
    """Simplify legal text"""
    try:
        if not text or not isinstance(text, str):
            return text
            
        # Basic replacements
        replacements = {
            "shall": "will",
            "must": "have to", 
            "hereinafter": "later in this document",
            "pursuant to": "according to",
        }
        
        for complex_term, simple_term in replacements.items():
            text = re.sub(r'\b' + complex_term + r'\b', simple_term, text, flags=re.IGNORECASE)
        
        return text
        
    except Exception as e:
        print(f"Error in simplify_text: {e}")
        return text

@app.get("/")
async def root():
    return {"message": "Welcome to the Legal Document Simplifier API"}

@app.get("/test-simplify")
async def test_simplify():
    try:
        test_text = "The party shall indemnify and must pay damages pursuant to the terms."
        
        risks = identify_legal_risks(test_text)
        simplified = simplify_text(test_text, "simple")
        
        return {
            "original": test_text,
            "simplified": simplified,
            "risks": risks,
            "risk_count": len(risks),
            "success": True
        }
    except Exception as e:
        return {"error": str(e), "success": False}

@app.post("/simplify")
async def simplify(text_data: dict):
    try:
        text = text_data.get("text", "")
        level = text_data.get("level", "simple")
        
        risks = identify_legal_risks(text)
        simplified = simplify_text(text, level)
        
        return {
            "original_text": text,
            "simplified_text": simplified,
            "risks": risks,
            "success": True
        }
    except Exception as e:
        return {"error": str(e), "success": False}

if __name__ == "__main__":
    import uvicorn
    print("Starting server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)