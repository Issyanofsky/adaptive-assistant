
import psycopg2
from psycopg2.extras import execute_values
import uuid
import json
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def seed_data():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("🌱 Seeding test data...")

        # --- 1. SEED A WORKER USER ---
        # Hardcoding the UUID so we can easily reference it in tests
        test_user_uuid = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
        
        cur.execute("""
            INSERT INTO users (
                user_id, user_type, preferred_tone, enabled_tasks, personality_preferences
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING;
        """, (
            test_user_uuid, 
            'worker', 
            'casual', 
            json.dumps(["QA", "schedule_meeting", "take_note"]), 
            json.dumps({"schedule_meeting": 0.8, "take_note": 0.5, "QA": 0.9})
        ))

        # --- 2. SEED DEFAULT STRATEGIES ---
        strategies = [
            (str(uuid.uuid4()), 'neutral', 0.5, 0.0),
            (str(uuid.uuid4()), 'urgency', 0.8, 0.0),
            (str(uuid.uuid4()), 'reward', 0.7, 0.0),
            (str(uuid.uuid4()), 'social_proof', 0.6, 0.0),
            (str(uuid.uuid4()), 'chunking', 0.7, 0.0)
        ]
        
        cur.executemany("""
            INSERT INTO strategies (strategy_id, name, base_weight, fatigue)
            VALUES (%s, %s, %s, %s);
        """, strategies)

        # --- 3. SEED MOOD FOR THE USER ---
        cur.execute("""
            INSERT INTO interaction_mood (id, user_id, task_type, valence, frustration, engagement, resistance)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (
            str(uuid.uuid4()),
            test_user_uuid,
            'schedule_meeting',
            -0.2,  # Slightly annoyed/negative
            0.6,   # High frustration
            0.4,   # Lower engagement
            0.7    # Highly resistant to scheduling right now
        ))

        # --- 4. SEED SAMPLE TASKS ---
        tasks = [
            (str(uuid.uuid4()), test_user_uuid, 'schedule_meeting', 'Book sync with Design Team', 0.6),
            (str(uuid.uuid4()), test_user_uuid, 'take_note', 'Document the API architecture', 0.4),
            (str(uuid.uuid4()), test_user_uuid, 'QA', 'Check Q1 product release notes', 0.7)
        ]
        
        cur.executemany("""
            INSERT INTO tasks (task_id, user_id, task_type, description, base_priority)
            VALUES (%s, %s, %s, %s, %s);
        """, tasks)

        conn.commit()
        print(f"✅ Seeding complete! Test User ID created: {test_user_uuid}")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        conn.rollback()
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    seed_data()

