import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.reembed_service import reembed_all_chunks

def main():
    print("Starting document chunk re-embedding process...")
    db = SessionLocal()
    try:
        result = reembed_all_chunks(db)
        print(f"Re-embedding complete: {result}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
