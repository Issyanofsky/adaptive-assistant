
import os
import json
from datetime import datetime

# Import all the individual files you and I have created
from redis_session import SessionManager # Renamed from redis.py to avoid python library conflicts
from ranking_task import rank_and_select_task
from qa_handler import QAHandler
from mood_tracker import MoodTracker
from llm_engine import AyaLLMEngine
from strategy_selector import StrategySelector
from database import get_db_connection

class AssistantStateMachine:
    def __init__(self):
        # Initialize connections and state managers
        self.redis = SessionManager()
        self.llm = AyaLLMEngine()
        
    def process_interaction(self, user_id: str, user_input: str) -> dict:
        """
        The Master State Loop.
        Takes user input and runs the adaptive assistant logic in Hebrew.
        """
        db_conn = get_db_connection()
        cur = db_conn.cursor()
        
        try:
            # --- STATE 1: Natural Language Understanding (Aya) ---
            analysis = self.llm.parse_user_input(user_input)
            detected_intent = analysis.get("detected_intent", "unknown")
            mood = analysis.get("mood", {"valence": 0.0, "frustration": 0.0, "engagement": 0.5, "resistance": 0.0})
            
            # --- STATE 2: Mood Tracking & Back-off Gates ---
            mood_tracker = MoodTracker(db_conn, self.redis)
            mood_tracker.update_session_mood(user_id, detected_intent, mood)
            
            # Check if user is too frustrated (Triggers 10 min break if over threshold)
            mood_tracker.apply_back_off_logic(user_id, mood)
            if self.redis.r.exists(f"session:{user_id}:back_off"):
                return {
                    "response": "אני מבינה שזה לא זמן טוב. נדבר מאוחר יותר כשתרצה.",
                    "intent": detected_intent,
                    "strategy": "back_off"
                }

            # --- STATE 3: Task Execution & Context Retrieval ---
            response_text = ""
            
            # If the user is asking a question (FAQ / QA)
            if detected_intent == "QA":
                qa = QAHandler(db_conn)
                response_text = qa.search_knowledge_base(user_id, user_input)
                
            # If it's a hard task or general chat, let's look at the queue
            else:
                # Calculate dynamic weights and select the highest priority task
                selected_task = rank_and_select_task(user_id, cur, self.redis.r)
                
                # Select the psychological strategy based on fatigue
                strategy_selector = StrategySelector(db_conn, self.redis.r)
                strategy = strategy_selector.select_best_strategy(user_id)
                
                if selected_task:
                    task_type = selected_task['task_type']
                    strat_name = strategy['strategy']
                    
                    # Log that this strategy was used to increase fatigue
                    strategy_selector.record_strategy_usage(strat_name)
                    
                    # Set a 5-minute cooldown so we don't nag them with the same task
                    self.redis.set_task_cooldown(user_id, task_type, seconds=300)
                    
                    # Formulate Response based on Strategy (You can pass this to Aya later to make it sound natural!)
                    response_text = f"זיהיתי שתרצה לטפל ב: {task_type}. גישה מומלצת: {strat_name}."
                else:
                    response_text = "אני כאן לעזור. במה נתחיל היום?"

            # --- STATE 4: History & Session Persistence ---
            self.redis.add_message(user_id, "user", user_input)
            self.redis.add_message(user_id, "assistant", response_text)

            return {
                "response": response_text,
                "intent": detected_intent,
                "strategy": strategy['strategy'] if 'strategy' in locals() else "neutral",
                "mood": mood
            }

        except Exception as e:
            print(f"Error in State Machine: {e}")
            return {"response": "מצטערת, משהו השתבש בעיבוד המידע.", "intent": "error"}
        finally:
            cur.close()
            db_conn.close()

# Quick local terminal test (Optional)
if __name__ == "__main__":
    machine = AssistantStateMachine()
    test_user = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    
    print("🤖 מפעיל את העוזרת האישית (מצב בדיקה)...")
    while True:
        user_text = input("אתה: ")
        if user_text.lower() in ['exit', 'quit']:
            break
        result = machine.process_interaction(test_user, user_text)
        print(f"עוזרת: {result['response']}\n")

