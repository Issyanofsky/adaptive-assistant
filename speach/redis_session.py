import redis
import json
import os
import time
from datetime import timedelta
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

class SessionManager:
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.db = int(os.getenv("REDIS_DB", 0))
        self.password = os.getenv("REDIS_PASSWORD", None)
        self.use_ssl = os.getenv("REDIS_SSL", "False").lower() == "true"
        self.session_ttl = timedelta(minutes=int(os.getenv("SESSION_TTL_MINUTES", 30)))
        self._connect()

    def _connect(self):
        """Initialize Redis connection with retry mechanism."""
        retries = 5
        for attempt in range(retries):
            try:
                self.r = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=True,
                    ssl=self.use_ssl
                )
                # Test connection
                self.r.ping()
                logging.info(f"✅ Connected to Redis at {self.host}:{self.port}")
                return
            except redis.ConnectionError as e:
                logging.warning(f"⚠️ Redis connection failed (attempt {attempt+1}/{retries}): {e}")
                time.sleep(2 ** attempt)  # exponential backoff
        raise ConnectionError("❌ Could not connect to Redis after multiple attempts")

    def _safe_execute(self, func, *args, **kwargs):
        """Wrap Redis commands to handle disconnects."""
        try:
            return func(*args, **kwargs)
        except (redis.ConnectionError, redis.TimeoutError):
            logging.warning("⚠️ Redis connection lost, reconnecting...")
            self._connect()
            return func(*args, **kwargs)

    # --- Conversation History ---
    def add_message(self, user_id: str, role: str, content: str):
        key = f"session:{user_id}:history"
        message = json.dumps({"role": role, "content": content})
        self._safe_execute(self.r.rpush, key, message)
        self._safe_execute(self.r.ltrim, key, -10, -1)
        self._safe_execute(self.r.expire, key, self.session_ttl)

    def get_history(self, user_id: str):
        key = f"session:{user_id}:history"
        messages = self._safe_execute(self.r.lrange, key, 0, -1)
        return [json.loads(m) for m in messages]

    # --- Current Mood ---
    def update_current_mood(self, user_id: str, mood_dict: dict):
        key = f"session:{user_id}:current_mood"
        self._safe_execute(self.r.hset, key, mapping=mood_dict)
        self._safe_execute(self.r.expire, key, self.session_ttl)

    def get_current_mood(self, user_id: str):
        key = f"session:{user_id}:current_mood"
        return self._safe_execute(self.r.hgetall, key)

    # --- Task Cooldowns ---
    def set_task_cooldown(self, user_id: str, task_type: str, seconds=300):
        key = f"session:{user_id}:suggested:{task_type}"
        self._safe_execute(self.r.setex, key, seconds, "true")

    def is_task_on_cooldown(self, user_id: str, task_type: str) -> bool:
        key = f"session:{user_id}:suggested:{task_type}"
        return self._safe_execute(self.r.exists, key) == 1