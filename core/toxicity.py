
from pathlib import Path

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

import re


def contains_disguised_abuse(text):
    cleaned_text = text.lower()

    substitutions = {
        "@": "a",
        "0": "o",
        "1": "i",
        "!": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "$": "s",
        "7": "t",
    }

    for old, new in substitutions.items():
        cleaned_text = cleaned_text.replace(old, new)

    disguised_patterns = [
        r"\ba\*{1,4}hole\b",
        r"\ba[\W_]*s[\W_]*s[\W_]*h[\W_]*o[\W_]*l[\W_]*e\b",
    ]

    return any(
        re.search(pattern, cleaned_text)
        for pattern in disguised_patterns
    )
