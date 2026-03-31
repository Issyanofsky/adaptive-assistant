How to Run
1. 
```bash
ollama pull aya-expanse:8b
```
2. 
 * Open your terminal in the folder where the file is saved.
 * Run the application using:
 ```bash
   streamlit run speach.py
```

# FULL DATA STRUCTURE FOR THE ADAPTIVE ASSISTANT
1️⃣ PostgreSQL Tables
A) Users Table

Stores user info, type, preferences, and limits.
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    user_type TEXT NOT NULL, -- client, worker, manager
    preferred_tone TEXT DEFAULT 'friendly', -- casual, formal, friendly
    enabled_tasks JSONB, -- ["QA", "schedule_meeting", "take_note"]
    personality_preferences JSONB, -- {"schedule_meeting":0.9,"take_note":0.7,"QA":0.5}
    max_daily_suggestions INT DEFAULT 5,
    back_off_threshold FLOAT DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```
B) Tasks Table

Core table for all tasks, dynamic weights, ranking, extracted data, thresholds, subtasks.
```sql
CREATE TABLE tasks (
    task_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    task_type TEXT NOT NULL, -- QA, schedule_meeting, take_note, reminder
    description TEXT,
    base_priority FLOAT DEFAULT 0.5,
    dynamic_weight FLOAT DEFAULT 0.0,
    threshold FLOAT DEFAULT 0.5,
    ranking INT,
    attempts INT DEFAULT 0,
    state TEXT DEFAULT 'pending', -- pending, suggested, completed, ignored
    subtasks JSONB, -- optional subtasks
    availability BOOLEAN DEFAULT TRUE, -- allowed for user type
    deadline TIMESTAMP,
    history JSONB, -- [{"timestamp":"...","action":"suggested","strategy":"urgency","response":"accepted"}]
    detected_intent TEXT, -- inferred from conversation
    intent_confidence FLOAT DEFAULT 0.0, -- confidence score 0-1
    extracted_entities JSONB, -- {"meeting_date":"2026-04-01","attendees":["Alice","Bob"]}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```
C) Interaction / Mood Table

Tracks user mood, engagement, resistance per task type.
```sql
CREATE TABLE interaction_mood (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    task_type TEXT,
    valence FLOAT DEFAULT 0.0, -- -1 sad → 1 happy
    frustration FLOAT DEFAULT 0.0, -- 0-1
    engagement FLOAT DEFAULT 0.5, -- 0-1
    resistance FLOAT DEFAULT 0.0, -- 0-1
    trend TEXT DEFAULT 'stable', -- improving, worsening, stable
    last_updated TIMESTAMP DEFAULT NOW()
);
```
D) Persuasion Strategies Table

Tracks strategies, fatigue, per-user effectiveness.
```sql
CREATE TABLE strategies (
    strategy_id UUID PRIMARY KEY,
    name TEXT NOT NULL, -- neutral, urgency, reward, social_proof, chunking
    base_weight FLOAT DEFAULT 0.7,
    fatigue FLOAT DEFAULT 0.0, -- overuse penalty
    per_user_effectiveness JSONB, -- {"u123":0.8}
    last_used TIMESTAMP
);
```
E) QA Context Tables

Used only if task is QA.

Local Context
```sql
CREATE TABLE local_context (
    context_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    content TEXT,
    source TEXT,
    confidence FLOAT DEFAULT 1.0,
    product_relevance BOOLEAN DEFAULT FALSE
);
```
Web Context
```sql
CREATE TABLE web_context (
    context_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    content TEXT,
    source TEXT,
    confidence FLOAT DEFAULT 0.5,
    product_relevance BOOLEAN DEFAULT FALSE
);
```
F) Interaction History Table

Stores user input, detected intent, extracted entities, mood, and assistant response.
```sql
CREATE TABLE interaction_history (
    interaction_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    task_id UUID REFERENCES tasks(task_id),
    timestamp TIMESTAMP DEFAULT NOW(),
    user_input TEXT,
    detected_intent TEXT, -- inferred task
    intent_confidence FLOAT DEFAULT 0.0,
    extracted_entities JSONB, -- {"meeting_date":"2026-04-01","attendees":["Alice","Bob"]}
    mood JSONB, -- {"valence":0.7,"frustration":0.2,"engagement":0.8,"resistance":0.3}
    strategy TEXT, -- persuasion used
    response TEXT, -- assistant message
    user_feedback TEXT,
    completion BOOLEAN DEFAULT FALSE
);
```
2️⃣ Redis / Session Memory (Short-Term)
Key	Value	Notes
recent_messages:{user_id}	List of last 20 messages	Tracks conversation context
recent_tasks:{user_id}	List of last 5 tasks suggested	For ranking & fatigue
current_mood:{user_id}	JSON	{"valence":0.7,"frustration":0.2,"engagement":0.8,"resistance":0.3}
temporary_flags:{user_id}	JSON	{"suppress_meeting_suggestions": true}
session_dynamic_weights:{user_id}	JSON	Calculated dynamic weights per task
last_intent:{user_id}	JSON	{"intent":"schedule_meeting","confidence":0.92,"entities":{"meeting_date":"2026-04-01"}}
3️⃣ Key Variables (All Needed)
Variable	Purpose
base_priority	Static importance of task
personality_preference	Assistant preference per task type
resistance	User resistance to task
mood_modifier	Adjustment for user mood
dynamic_weight	Weight for task suggestion
threshold	Minimum weight to suggest task
ranking	Rank among tasks
attempts	Times task was suggested
availability	Task allowed for user type
strategy	Persuasion strategy used
fatigue	Overuse of strategy
max_daily_suggestions	Limit suggestions per day
back_off_threshold	Stop suggesting if resistance > threshold
valence	Happiness/sadness level
engagement	User engagement level
frustration	User frustration level
trend	Mood trend: improving/worsening/stable
detected_intent	Inferred user intent
intent_confidence	Confidence in intent detection
extracted_entities	Only relevant task data
4️⃣ Task Selection Loop (Simplified)
```python
for task in user_tasks:
    if not task.availability:
        continue

    # Adjust for intent match
    intent_match_factor = 1.2 if session.last_intent['intent'] == task.task_type else 1.0
    dynamic_weight = (
        task.base_priority
        * personality_pref[task.task_type]
        * (1 - mood['resistance'])
        * mood_modifier
        * intent_match_factor
    )
    task.dynamic_weight = dynamic_weight

eligible_tasks = [t for t in user_tasks if t.dynamic_weight > t.threshold]
eligible_tasks.sort(key=lambda x: x.dynamic_weight, reverse=True)

for i, t in enumerate(eligible_tasks):
    t.ranking = i + 1

top_task = eligible_tasks[0] if eligible_tasks else None
strategy = select_best_strategy(user, top_task)
```


          ┌───────────────────────────────┐
          │           USER                │
          │  - Sends messages / queries  │
          │  - Responds to suggestions   │
          └─────────────┬────────────────┘
                        │
                        ▼
          ┌───────────────────────────────┐
          │       LLM / AI Engine         │
          │  - Detect intent & entities  │
          │  - Select task & strategy    │
          │  - Generate response message │
          └─────────────┬────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────────────┐      ┌───────────────────────┐
│   PostgreSQL Database  │      │     Redis / Session    │
│-----------------------│      │-----------------------│
│ USERS                 │      │ recent_messages:{uid} │
│ TASKS                 │      │ recent_tasks:{uid}    │
│ INTERACTION_HISTORY   │      │ current_mood:{uid}    │
│ INTERACTION_MOOD      │      │ temporary_flags:{uid} │
│ STRATEGIES            │      │ session_dynamic_weights│
│ LOCAL_CONTEXT / WEB_CONTEXT│ │ last_intent:{uid}     │
└─────────────┬─────────┘      └─────────────┬─────────┘
              │                              │
              └───────────────┬──────────────┘
                              ▼
                    ┌───────────────────────┐
                    │ TASK SELECTION LOOP    │
                    │-----------------------│
                    │ - Load user, tasks, mood │
                    │ - Apply weights & thresholds │
                    │ - Rank tasks               │
                    │ - Choose persuasion strategy│
                    │ - Update session & db      │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────┐
                    │    Assistant Action    │
                    │-----------------------│
                    │ - Send message         │
                    │ - Suggest task         │
                    │ - Take notes           │
                    │ - Set meetings         │
                    └───────────────────────┘


# 🗺️ Adaptive AI Assistant: Master Project Checklist
​🏁 Phase 1: Architecture & Environment Setup (Where we are starting)

    ​[ ] 1.1 Define system architecture (Data flows between LLM, DB, and Redis).
    ​[ ] 1.2 Setup local development environment (Python, PostgreSQL, Redis).
    ​[ ] 1.3 Establish project folder structure.

​🗄️ Phase 2: Database & Memory Layer

    ​[ ] 2.1 Initialize PostgreSQL tables (Users, Tasks, Mood, Strategies, QA Context).
    ​[ ] 2.2 Insert seed/mock data (Sample users, baseline strategies, tasks).
    ​[ ] 2.3 Design Redis Session Memory schema (TTL keys for recent messages, active mood).

​🧠 Phase 3: The Task Selection Loop (The Core Brain)

    ​[ ] 3.1 Define the task mathematical variables in code.
    ​[ ] 3.2 Write the dynamic weight calculation algorithm (combining base priority, personality, mood, and resistance).
    ​[ ] 3.3 Implement threshold filtering and ranking logic.
    ​[ ] 3.4 Create the Persuasion Strategy selector (incorporating fatigue and historical effectiveness).

​🤖 Phase 4: Intent, Entities & QA Handling

    ​[ ] 4.1 Design LLM prompt for Intent Detection and Entity Extraction.
    ​[ ] 4.2 Build the QA retrieval logic (Check Local Context \rightarrow Check Web Context \rightarrow Fallback).

​📈 Phase 5: Adaptive Mood & Fatigue Tracking

    ​[ ] 5.1 Build the state updater for user valence, frustration, and engagement.
    ​[ ] 5.2 Implement the strategy fatigue decay (cooling down strategies over time).

​🔌 Phase 6: Python Orchestration & API

    ​[ ] 6.1 Create the master execution loop (The workflow: Input \rightarrow Process \rightarrow Output).
    ​[ ] 6.2 Build a lightweight API (like FastAPI) or CLI to chat with the system.

​🧪 Phase 7: Examples, Testing & Free Tier Optimization

    ​[ ] 7.1 Run end-to-end simulation tests with sample JSON outputs.
    ​[ ] 7.2 Optimize prompts for free-tier LLMs


## 📁 Project Structure & File Purposes

### 🧠 Core Assistant Logic (Root Directory)
* **`main.py`** - The Master State Machine. Orchestrates the flow of user input through intent analysis, mood tracking, task execution, and response generation.
* **`llm_engine.py`** - Connects to the local, free **Aya** model via Ollama. It parses Hebrew user input to extract intent, entities, and psychological mood states.
* **`task_handler.py'** - manage the Tasks
* **`ranking_task.py`** - Calculates dynamic priority scores for pending tasks based on base weights, user preferences, and live mood modifiers.
* **`strategy_selector.py`** - Evaluates persuasion strategies (Urgency, Reward, Chunking, etc.) against strategy fatigue and user effectiveness scores.
* **`qa_handler.py`** - Manages context retrieval. It queries the PostgreSQL local or web context tables to answer user questions with local or scraped data and outside WEB.
* **`mood_tracker.py`** - Analyzes psychological trends (improving/worsening) and handles the critical "back-off" cooldown logic to prevent nagging frustrated users.
* **`database.py`** - Centralized helper script to establish standard pooling or direct connections to the PostgreSQL database.
* **`redis_session.py`** - Oversees all active user session variables, live mood states, task cooldowns, and short-term chat history in Redis.

### 🌐 Web Server & Interface
* **`app.py`** - The FastAPI backend web server that acts as a secure, fast API bridge between your UI and your Python files.
* **`html/`** - The Frontend folder containing the professional, "Glassmorphism" UI with dark mode, full RTL Hebrew support, and native two-way Web Speech (STT and TTS) API integration.

### 🐳 Infrastructure & Database Management
* **`adaptive_assistant_redis/`** - Holds your Docker Compose setup, persistent data volume, and configuration for running Redis in a sandbox.
* **`sql_create_schema.py`** & **`seed_data.py`** - Used to construct your PostgreSQL tables and load test mock data for your system to pull from.
* **`requirements.txt`** - The complete list of python libraries (like FastAPI, psycopg2, redis, and uvicorn) needed to run this stack.
* **`populate_qa.py'** - populate data for QA. imports data and set the knowlage needed by the model to answer.

# 🚀 How to Run the Project (Full Guide)
Here is your complete, master startup guide updated with all the changes we just made. You will open three separate terminals (or terminal tabs).
Step 1: Fire up Redis and PostgresSql
Navigate to your Redis folder and start the Docker container in the background.
cd speach/adaptive_assistant_redis
docker-compose up -d

Step 2: Fire up your local LLM
Open a new terminal and start your local Aya model so the backend server can access it for Hebrew processing.
ollama run aya

Step 3: Start the Backend and Frontend Server
Open a new terminal in your root speach/ folder. First, ensure your dependencies are installed and properly updated:
cd speach
pip install -r requirements.txt

(Note: If you haven't run your database schema and seed data files yet, do that now with python sql_create_schema.py and python seed_data.py)
Now, start the FastAPI application:
uvicorn app:app --reload

Step 4: Open the Web Interface
Look at your terminal logs from Step 3. You will see a log saying Uvicorn running on http://127.0.0.1:8000.
 * Open your Google Chrome or Edge web browser.
 * Go directly to: http://127.0.0.1:8000
FastAPI is now securely serving your webpage! Click on the microphone icon to speak to your assistant or type out a response.