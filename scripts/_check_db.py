"""Quick DB check script."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

pw = os.getenv("DB_PASSWORD")
url = f"postgresql://postgres:{pw}@localhost:5432/phoenix_guardian"
engine = create_engine(url)

with engine.connect() as conn:
    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"))
    tables = [row[0] for row in result]
    print(f"Tables ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")
    
    if "users" in tables:
        result = conn.execute(text("SELECT email, role FROM users ORDER BY email"))
        print("\nUsers:")
        for row in result:
            print(f"  - {row[0]} ({row[1]})")
    
    if "patients" in tables:
        result = conn.execute(text("SELECT id, name FROM patients LIMIT 10"))
        print("\nPatients:")
        for row in result:
            print(f"  - {row[0]}: {row[1]}")
