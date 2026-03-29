
import psycopg2
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

def create_schema():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("🛠️ Dropping old tables (if they exist) to ensure a clean slate...")
        cur.execute("""
            DROP TABLE IF EXISTS interaction_history CASCADE;
            DROP TABLE IF EXISTS web_context CASCADE;
            DROP TABLE IF EXISTS local_context CASCADE;
            DROP TABLE IF EXISTS strategies CASCADE;
            DROP TABLE IF EXISTS interaction_mood CASCADE;
            DROP TABLE IF EXISTS tasks CASCADE;
            DROP TABLE IF EXISTS users CASCADE;
        """)

        print("🏗️ Creating fresh tables...")

        # 1. Users Table
        cur.execute("""
            CREATE TABLE users (
                user_id UUID PRIMARY KEY,
                user_type TEXT NOT NULL, 
                preferred_tone TEXT DEFAULT 'friendly', 
                enabled_tasks JSONB, 
                personality_preferences JSONB, 
                max_daily_suggestions INT DEFAULT 5,
                back_off_threshold FLOAT DEFAULT 0.8,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 2. Tasks Table
        cur.execute("""
            CREATE TABLE tasks (
                task_id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(user_id),
                task_type TEXT NOT NULL, 
                description TEXT,
                base_priority FLOAT DEFAULT 0.5,
                dynamic_weight FLOAT DEFAULT 0.0,
                threshold FLOAT DEFAULT 0.5,
                ranking INT,
                attempts INT DEFAULT 0,
                state TEXT DEFAULT 'pending', 
                subtasks JSONB, 
                availability BOOLEAN DEFAULT TRUE, 
                deadline TIMESTAMP,
                history JSONB, 
                detected_intent TEXT, 
                intent_confidence FLOAT DEFAULT 0.0, 
                extracted_entities JSONB, 
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 3. Interaction / Mood Table
        cur.execute("""
            CREATE TABLE interaction_mood (
                id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(user_id),
                task_type TEXT,
                valence FLOAT DEFAULT 0.0, 
                frustration FLOAT DEFAULT 0.0, 
                engagement FLOAT DEFAULT 0.5, 
                resistance FLOAT DEFAULT 0.0, 
                trend TEXT DEFAULT 'stable', 
                last_updated TIMESTAMP DEFAULT NOW()
            );
        """)

        # 4. Persuasion Strategies Table
        cur.execute("""
            CREATE TABLE strategies (
                strategy_id UUID PRIMARY KEY,
                name TEXT NOT NULL, 
                base_weight FLOAT DEFAULT 0.7,
                fatigue FLOAT DEFAULT 0.0, 
                per_user_effectiveness JSONB, 
                last_used TIMESTAMP
            );
        """)

        # 5. Local Context Table
        cur.execute("""
            CREATE TABLE local_context (
                context_id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(user_id),
                content TEXT,
                source TEXT,
                confidence FLOAT DEFAULT 1.0,
                product_relevance BOOLEAN DEFAULT FALSE
            );
        """)

        # 6. Web Context Table
        cur.execute("""
            CREATE TABLE web_context (
                context_id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(user_id),
                content TEXT,
                source TEXT,
                confidence FLOAT DEFAULT 0.5,
                product_relevance BOOLEAN DEFAULT FALSE
            );
        """)

        # 7. Interaction History Table
        cur.execute("""
            CREATE TABLE interaction_history (
                interaction_id UUID PRIMARY KEY,
                user_id UUID REFERENCES users(user_id),
                task_id UUID REFERENCES tasks(task_id),
                timestamp TIMESTAMP DEFAULT NOW(),
                user_input TEXT,
                detected_intent TEXT, 
                intent_confidence FLOAT DEFAULT 0.0,
                extracted_entities JSONB, 
                mood JSONB, 
                strategy TEXT, 
                response TEXT, 
                user_feedback TEXT,
                completion BOOLEAN DEFAULT FALSE
            );
        """)

        conn.commit()
        print("✅ Database schema created successfully!")
        
    except Exception as e:
        print(f"❌ Error creating schema: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    create_schema()

