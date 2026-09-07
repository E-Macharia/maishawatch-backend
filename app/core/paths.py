from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / 'data'
ML_DATA_DIR = DATA_DIR / 'ml'
MODELS_DIR = PROJECT_ROOT / 'models'
STORAGE_DIR = PROJECT_ROOT / 'storage'
DB_FILE = STORAGE_DIR / 'maishawatch.db'
