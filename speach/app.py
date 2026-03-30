
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

# Import the files from your directory
from redis_session import SessionManager
from ranking_task import rank_and_select_task
from qa_handler import QAHandler
from mood_tracker import MoodTracker
from llm_engine import AyaLLMEngine
from strategy_selector import StrategySelector
from database import get_db_connection

app = FastAPI(title="Adaptive Assistant API")

# Allow Frontend to talk to Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize our modules
redis_session = SessionManager()
llm = AyaLLMEngine()

class ChatRequest(BaseModel):
    user_id: str
    message: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    db_conn = get_db_connection()
    cur = db_conn.cursor()
    
    # 1. Parse user input using Aya (Intents, Mood, Entities)
    analysis = llm.parse_user_input(request.message)
    detected_intent = analysis.get("detected_intent")
    mood = analysis.get("mood")
    
    # 2. Update Mood Tracker
    mood_tracker = MoodTracker(db_conn, redis_session)
    mood_tracker.update_session_mood(request.user_id, detected_intent, mood)
    mood_tracker.apply_back_off_logic(request.user_id, mood)
    
    # --- Politeness Guard Check ---
    # List of common Hebrew & English greetings to check against
    greetings = ["שלום", "היי", "בוקר טוב", "ערב טוב", "אהלן", "hello", "hi"]
    is_greeting = any(greet in request.message.lower() for greet in greetings)
    
    response_text = ""
    strategy_used = "Conversational" # Default strategy fallback for greetings

    # 3. Handle QA specifically if requested (Skip if it's just a simple hello!)
    if detected_intent == "QA" and not is_greeting:
        qa = QAHandler(db_conn)
        response_text = qa.search_knowledge_base(request.user_id, request.message)
    
    # If it is a greeting, prioritize a friendly response over pushing a task
    if is_greeting and not response_text:
        response_text = "שלום! במה אוכל לעזור לך היום?"
    
    # Otherwise, execute the normal background business logic
    else:
        # 4. Rank Tasks and Select Strategy
        selected_task = rank_and_select_task(request.user_id, cur, redis_session.r)
        strategy_selector = StrategySelector(db_conn, redis_session.r)
        strategy = strategy_selector.select_best_strategy(request.user_id)
        strategy_used = strategy["strategy"]
        
        # Formulate fallback response if QA had no answers or wasn't triggered
        if not response_text:
            response_text = f"משימה מתוזמנת: {selected_task['task_type'] if selected_task else 'כללי'}. אסטרטגיה: {strategy_used}."
        
    # 5. Save to Redis History
    redis_session.add_message(request.user_id, "user", request.message)
    redis_session.add_message(request.user_id, "assistant", response_text)

    # Clean up DB connections safely before returning the HTTP response
    cur.close()
    db_conn.close()

    return {
        "response": response_text,
        "detected_intent": detected_intent,
        "mood": mood,
        "strategy_used": strategy_used
    }

# This mounts your 'html' folder to the root URL (/)
# It handles loading index.html automatically and serving your CSS and JS!
app.mount("/", StaticFiles(directory="html", html=True), name="html")

