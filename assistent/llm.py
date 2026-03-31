# llm.py
import json


class LLMCommunicator:
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    def generate_json(self, prompt: str, schema: dict) -> dict:
        """
        Enforces structured JSON output based on schema.
        """

        full_prompt = f"""
You are a JSON generator.

Return ONLY valid JSON.
No explanations, no text.

Required schema:
{json.dumps(schema, indent=2)}

Task:
{prompt}
"""

        raw = self._call_model(full_prompt)

        try:
            parsed = json.loads(raw)
        except Exception:
            print("INVALID JSON FROM LLM:", raw)
            return {}

        # Optional: validate keys exist
        for key in schema.keys():
            if key not in parsed:
                parsed[key] = None

        return parsed

    def _call_model(self, prompt: str) -> str:
        """
        Replace this with real LLM call.
        For now: deterministic mock.
        """

        # 🔧 Minimal mock so system works
        if "intent" in prompt:
            return json.dumps({
                "intent": "schedule_meeting",
                "meeting_subject": "Team Sync",
                "date": "2026-03-31",
                "time": None,
                "location": None,
                "participants": None
            })

        if "next_question" in prompt:
            return json.dumps({
                "next_question": "What time should the meeting be?"
            })

        return "{}"