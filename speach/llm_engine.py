import json
import ollama

class AyaLLMEngine:
    def __init__(self, redis_conn):
        # We use the 'aya' model via Ollama (100% free and local)
        self.model_name = 'aya'
        self.redis = redis_conn

    def parse_user_input(self, user_input: str, chat_history) -> dict:
        """
        Sends the Hebrew user input to Aya to extract intent, entities, and mood.
        """
        formatted_history = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in chat_history]
        )
        system_prompt = f"""
        אתה מנתח שפה עבור עוזרת אישית חכמה.

        היסטוריית שיחה:
        {formatted_history}

        הוראות מחמירות:
        1. נתח את הקלט של המשתמש והחזר **רק אובייקט JSON תקין** במבנה הבא (ללא שום טקסט נוסף וללא markdown):

        {{
            "detected_intent": "schedule_meeting" | "info_metting" | "cancel_metting" | "take_note" | "info_note" | "cancel_note" | "conversation" | "reminder" | "info_reminder" | "cancel_reminder" | "unknown" ,
            "intent_confidence": 0.0 to 1.0,
            "extracted_entities": {{ "meeting_date": "YYYY-MM-DD", "attendees": [] }},
            "mood": {{
                "valence": -1.0 to 1.0,
                "frustration": 0.0 to 1.0,
                "engagement": 0.0 to 1.0,
                "resistance": 0.0 to 1.0
            }}
        }}


        2. אם אין התאמה מוחלטת לאחד מה-intents: "schedule_meeting",  "info_metting",  "cancel_metting", "take_note", "info_note", "cancel_note", "conversation", "reminder", "info_reminder", "cancel_reminder" החזר תמיד:
        "detected_intent": "unknown"

        3. **אסור** להחזיר טקסט חופשי, markdown, הסברים או תוספות כלשהן. רק JSON.

        4. שמור על מבנה מדויק, וכל ערך צריך להיות תקין (null או array ריק במקום חסר מידע).
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_input}
                ]
            )
            
            clean_content = response['message']['content'].strip()
            if clean_content.startswith("```json"):
                clean_content = clean_content.split("```json")[1].split("```")[0].strip()
            elif clean_content.startswith("```"):
                clean_content = clean_content.split("```")[1].strip()


            return json.loads(clean_content)
            
        except Exception as e:
            print(f"Error calling Aya: {e}")
            return {
                "detected_intent": "unknown",
                "intent_confidence": 0.0,
                "extracted_entities": {},
                "mood": {"valence": 0.0, "frustration": 0.0, "engagement": 0.5, "resistance": 0.0}
            }

    # --- NEW METHOD ADDED HERE ---
    def generate_polite_response(self, user_message: str, strategy: str, mood: dict, knowledge_base_data: str, current_task: dict, chat_history: list) -> str:
        """
        Uses Aya to generate a final human-like, polite response based on the full session context.
        """
        print(f"[DEBUG] enter polite LLM")
        formatted_history = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in chat_history]
        )
        # Formulate a context block of what we know about the task
        task_info = f"משימה מתוזמנת: {current_task['task_type']}" if current_task else "אין משימה מתוזמנת כרגע"
        
        system_prompt = f"""
        אתה העוזרת האישית של המשתמש. תפקידך לענות לו בצורה אנושית, מנומסת ומקצועית בעברית טבעית.

        היסטוריית שיחה:
        {formatted_history}
                        
        השתמש בנתונים הבאים כדי להתאים אישית את התגובה שלך:
        - האסטרטגיה שנבחרה: {strategy}
        - מצב הרוח של המשתמש: {json.dumps(mood, ensure_ascii=False)}
        - נתוני בסיס הידע שנמצאו (אם בכלל): {knowledge_base_data}
        - משימת הרקע הנוכחית: {task_info}
        
        הוראות חשובות:
        1. דבר בטבעיות. אל תזכיר במפורש מושגים טכניים כמו "אסטרטגיה", "משימה מתוזמנת" או "מצב רוח" בתשובה שלך.
        2. אם בסיס הידע סיפק תשובה, שלב אותה בצורה חלקה ומנומסת.
        3. אם המשתמש מתוסכל (frustration גבוה), היה אמפתי ומכיל יותר.
        """

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ]
            )
            return response['message']['content'].strip()
            
        except Exception as e:
            print(f"Error generating response from Aya: {e}")
            # Safe fallback if LLM is down
            if knowledge_base_data:
                return knowledge_base_data
            return "אני מצטערת, נתקלתי בבעיה קלה. איך אוכל לעזור לך?"
        
    def format_history(history: list) -> str:
        return "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in history]
    )


