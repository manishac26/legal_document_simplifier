import re

def simplify_text(text, level="simple"):
    """
    Simplify legal text based on complexity level
    This is a placeholder - in a real app, you'd use NLP models
    """
    # Basic text cleaning
    text = re.sub(r'\s+', ' ', text).strip()
    
    if level == "simple":
        # Very basic simplification - replace complex terms
        replacements = {
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
        }
        
        for complex_term, simple_term in replacements.items():
            text = text.replace(complex_term, simple_term)
            
    elif level == "moderate":
        # More aggressive simplification
        replacements = {
            "not less than": "at least",
            "not more than": "at most",
            "in the event that": "if",
            "for the purpose of": "to",
            "with respect to": "about",
            "prior to": "before",
            "subsequent to": "after",
            "in accordance with": "by",
            "shall be deemed": "is considered",
        }
        
        for complex_term, simple_term in replacements.items():
            text = text.replace(complex_term, simple_term)
            
    # For advanced level, you might want to integrate with an NLP API
    
    return text