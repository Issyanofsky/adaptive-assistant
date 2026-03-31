from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import sys
import asyncio
from contextlib import asynccontextmanager

from redis_session import SessionManager
from ranking_task import rank_and_select_task
from qa_handler import QAHandler
from mood_tracker import MoodTracker
from llm_engine import AyaLLMEngine
from task_handler import UnifiedTaskExecutor
from strategy_selector import StrategySelector
from database import get_db_connection

# --- WINDOWS BUG FIX ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    detected_intent = analysis.get("detected_intent", "unknown")
    mood = analysis.get("mood", {"valence": 0.0, "frustration": 0.0, "engagement": 0.5, "resistance": 0.0})
    
    # 2. Update Mood Tracker
    mood_tracker = MoodTracker(db_conn, redis_session)
    mood_tracker.update_session_mood(request.user_id, detected_intent, mood)
    mood_tracker.apply_back_off_logic(request.user_id, mood)
    
    # --- Politeness Guard Check ---
    greetings = ["שלום", "היי", "בוקר טוב", "ערב טוב", "אהלן", "hello", "hi"]
    is_greeting = any(greet in request.message.lower() for greet in greetings)
    
    # 3. Fetch Knowledge Base Answers (if any)
    qa = QAHandler(db_conn)
    knowledge_base_data = await qa.search_knowledge_base(request.user_id, request.message)
    
    # Clean fallback if greeting triggered a non-result
    if is_greeting and not knowledge_base_data:
        knowledge_base_data = ""
        
    # 4. Rank Tasks and Select Strategy
    selected_task = rank_and_select_task(request.user_id, cur, redis_session.r)
    strategy_selector = StrategySelector(db_conn, redis_session.r)
    strategy = strategy_selector.select_best_strategy(request.user_id)
    strategy_used = strategy.get("strategy", "Conversational")
    
    # --- 5. THE AI SYNTHESIS OF THE FINAL ANSWER ---
    # We feed EVERYTHING we gathered into Aya to generate a custom, polite response
    response_text = llm.generate_polite_response(
        user_message=request.message,
        strategy=strategy_used,
        mood=mood,
        knowledge_base_data=knowledge_base_data,
        current_task=selected_task
    )

    # 6. Save to Redis History
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

app.mount("/", StaticFiles(directory="html", html=True), name="html")