import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.services.fraud_model_training import train_iforest_and_save  # noqa: E402


if __name__ == "__main__":
    db = SessionLocal()
    try:
        output_path = train_iforest_and_save(db=db)
    finally:
        db.close()
    print(f"[OK] Isolation forest trained and saved to {output_path}")
