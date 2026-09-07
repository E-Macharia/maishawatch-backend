# run.py
import uvicorn
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["app"]
    )
