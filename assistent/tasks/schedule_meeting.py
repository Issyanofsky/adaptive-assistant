# tasks/schedule_meeting.py

TASK_NAME = "schedule_meeting"

REQUIRED_VARS = ["meeting_subject", "date", "time"]

OPTIONAL_VARS = ["location", "participants"]

INITIAL_STATE = "COLLECTING_DATA"


def extraction_schema():
    return {
        "intent": "string",
        "meeting_subject": "string",
        "date": "string",
        "time": "string",
        "location": "string",
        "participants": "string"
    }


def extraction_prompt(user_input: str):
    return f"""
Extract relevant fields from this input:

"{user_input}"
"""


def next_step_schema():
    return {
        "next_question": "string"
    }


def next_step_prompt(current_data: dict, missing_field: str):
    return f"""
We are scheduling a meeting.

Current data:
{current_data}

Missing:
{missing_field}

Ask the user for the missing field.
"""