
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
