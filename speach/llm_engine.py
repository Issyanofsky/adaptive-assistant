
import json
import ollama

class AyaLLMEngine:
    def __init__(self):
        # We use the 'aya' model via Ollama (100% free and local)
        self.model_name = 'aya'

    def parse_user_input(self, user_input: str) -> dict:
        """
        Sends the Hebrew user input to Aya to extract intent, entities, and mood.
        """
        
        system_prompt = """
        אתה מנתח שפה עבור עוזרת אישית חכמה.
        נתח את הקלט של המשתמש והחזר אך ורק אובייקט JSON תקין במבנה הבא (ללא שום טקסט נוסף וללא סימני markdown):
        {
            "detected_intent": "schedule_meeting" | "take_note" | "QA" | "reminder" | "unknown",
            "intent_confidence": 0.0 to 1.0,
            "extracted_entities": { "meeting_date": "YYYY-MM-DD", "attendees": [] },
            "mood": {
                "valence": -1.0 to 1.0,
                "frustration": 0.0 to 1.0,
                "engagement": 0.0 to 1.0,
                "resistance": 0.0 to 1.0
            }
        }

        **אם השאלה או הבקשה של המשתמש לא מתאימה לאחת מהקטגוריות המוגדרות ("schedule_meeting", "take_note", "QA", "reminder"), יש להחזיר את intent כ-"unknown".**
        """
        
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_input}
                ]
            )
            
            # Clean response from potential markdown code blocks
            clean_content = response['message']['content'].strip()
            if clean_content.startswith("```json"):
                clean_content = clean_content.split("```json")[1].split("```")[0].strip()
            elif clean_content.startswith("```"):
                clean_content = clean_content.split("```")[1].strip()

            return json.loads(clean_content)
            
        except Exception as e:
            print(f"Error calling Aya: {e}")
            # Safe fallback if local LLM fails or hallucinates JSON
            return {
                "detected_intent": "unknown",
                "intent_confidence": 0.0,
                "extracted_entities": {},
                "mood": {"valence": 0.0, "frustration": 0.0, "engagement": 0.5, "resistance": 0.0}
            }

