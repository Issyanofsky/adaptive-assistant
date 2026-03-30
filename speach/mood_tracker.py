
from datetime import datetime
import json

class MoodTracker:
    def __init__(self, db_conn, redis_conn):
        self.db = db_conn
        self.redis = redis_conn

    def update_session_mood(self, user_id: str, task_type: str, new_mood: dict):
        """
        Updates the mood in both Redis (for instant session retrieval) 
        and PostgreSQL (for long-term trend calculation).
        """
        cur = self.db.cursor()
        
        # 1. Update Redis live session state
        redis_key = f"session:{user_id}:current_mood"
        self.redis.r.hset(redis_key, mapping=new_mood)
        # Session auto-expires after 30 minutes of inactivity
        self.redis.r.expire(redis_key, 1800) 
        
        # 2. Get previous mood from Postgres to calculate the trend
        cur.execute("""
            SELECT valence, frustration, last_updated 
            FROM interaction_mood 
            WHERE user_id = %s AND task_type = %s
            ORDER BY last_updated DESC LIMIT 1
        """, (user_id, task_type))
        
        prev_mood = cur.fetchone()
        trend = 'stable'
        
        if prev_mood:
            prev_valence, prev_frustration, _ = prev_mood
            
            # Simple heuristic to determine the psychological trend
            if new_mood['valence'] > prev_valence and new_mood['frustration'] < prev_frustration:
                trend = 'improving'
            elif new_mood['valence'] < prev_valence or new_mood['frustration'] > prev_frustration:
                trend = 'worsening'
        
        # 3. Update or Insert the long-term PostgreSQL table
        cur.execute("""
            INSERT INTO interaction_mood (
                id, user_id, task_type, valence, frustration, engagement, resistance, trend, last_updated
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (id) DO NOTHING;
        """, (
            user_id,
            task_type,
            new_mood['valence'],
            new_mood['frustration'],
            new_mood['engagement'],
            new_mood['resistance'],
            trend
        ))
        
        self.db.commit()
        return trend

    def apply_back_off_logic(self, user_id: str, mood: dict):
        """
        If the user is highly resistant or frustrated, we trip a cooldown 
        so the assistant stops suggesting tasks for a short while.
        """
        # Fetch the user's back_off_threshold from Postgres
        cur = self.db.cursor()
        cur.execute("SELECT back_off_threshold FROM users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        threshold = result[0] if result else 0.8
        
        # If frustration or resistance passes the threshold, activate back-off
        if mood['frustration'] >= threshold or mood['resistance'] >= threshold:
            # Set a global suggest-lock for 10 minutes in Redis
            self.redis.setex(f"session:{user_id}:back_off", 600, "active")
            print(f"🛑 Back-off triggered for user {user_id}. Resting for 10 minutes.")

