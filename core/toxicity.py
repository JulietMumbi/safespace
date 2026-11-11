
from pathlib import Path
import html
import re

import joblib
from django.conf import settings


MODEL_PATH = (
    Path(settings.BASE_DIR)
    / "ml_models"
    / "safespace_toxicity_model.joblib"
)


def load_toxicity_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"SafeSpace toxicity model not found at: {MODEL_PATH}"
        )
    return joblib.load(MODEL_PATH)


def normalize_text(text):
    text = html.unescape(str(text).lower())

    substitutions = {
        "@": "a", "0": "o", "1": "i",
        "!": "i", "3": "e", "4": "a",
        "5": "s", "$": "s", "7": "t"
    }

    for old, new in substitutions.items():
        text = text.replace(old, new)

    # Remove separators only when they occur inside words.
    text = re.sub(
        r"(?<=[a-z])[^a-z\s]+(?=[a-z])",
        "",
        text
    )

    # Reduce repeated characters.
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)

    return text



def contains_disguised_abuse(text):
    normalized = normalize_text(text)

    abusive_words = [
        "asshole",
        "idiot",
        "moron",
        "stupid",
        "worthless",
        "useless",
        "pathetic",
    ]

    return any(
        re.search(rf"\b{re.escape(word)}\b", normalized)
        for word in abusive_words
    )
    

def contains_self_harm_concern(text):
    normalized = normalize_text(text)

    concern_patterns = [
        r"\bkill myself\b",
        r"\bend my life\b",
        r"\bwant to die\b",
        r"\bdont want to live\b",
        r"\bdo not want to live\b",
        r"\bhurt myself\b",
        r"\bsuicidal\b",
        r"\btake my own life\b",
        r"\bself harm\b",
        r"\bselfharm\b",
    ]

    return any(
        re.search(pattern, normalized)
        for pattern in concern_patterns
    )

