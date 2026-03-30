

import json

def calculate_mood_modifier(mood: dict) -> float:
    """
    Translates raw mood floats into a multiplier between 0.0 and 1.0.
    High frustration and resistance will lower the multiplier.
    """
    if not mood:
        return 0.5  # Neutral default
        
    valence = float(mood.get('valence', 0.0))
    frustration = float(mood.get('frustration', 0.0))
    resistance = float(mood.get('resistance', 0.0))
    
    # Simple heuristic: high frustration/resistance tank the score.
    # Good valence boosts it slightly.
    base_mood = 0.5 + (valence * 0.2)
    penalties = (frustration * 0.2) + (resistance * 0.3)
    
    return max(0.0, min(1.0, base_mood - penalties))

def rank_and_select_task(user_id: str, db_cursor, redis_conn):
    """
    Pulls tasks, calculates dynamic weights, filters by threshold, 
    and returns the top-ranked task.
    """
    # 1. Fetch User Preferences from Postgres
    db_cursor.execute(
        "SELECT personality_preferences, max_daily_suggestions FROM users WHERE user_id = %s", 
        (user_id,)
    )
    user_data = db_cursor.fetchone()
    personality_prefs = user_data[0] if user_data[0] else {}
    
    # 2. Fetch Live Mood from Redis
    raw_mood = redis_conn.hgetall(f"session:{user_id}:current_mood")
    mood_modifier = calculate_mood_modifier(raw_mood)
    
    # 3. Fetch All Pending Tasks for User from Postgres
    db_cursor.execute(
        "SELECT task_id, task_type, base_priority, threshold FROM tasks WHERE user_id = %s AND state = 'pending'",
        (user_id,)
    )
    pending_tasks = db_cursor.fetchall()
    
    scored_tasks = []
    
    for task in pending_tasks:
        task_id, task_type, base_priority, threshold = task
        
        # Check Redis for fatigue/cooldown
        if redis_conn.exists(f"session:{user_id}:suggested:{task_type}"):
            continue  # Skip task if suggested too recently
            
        # Get personality preference for this specific task type
        pref_score = personality_prefs.get(task_type, 0.5)
        
        # Calculate Dynamic Weight (The Formula)
        dynamic_weight = (base_priority * 0.4) + (pref_score * 0.4) + (mood_modifier * 0.2)
        
        # Apply Threshold Gate
        if dynamic_weight >= threshold:
            scored_tasks.append({
                "task_id": task_id,
                "task_type": task_type,
                "dynamic_weight": round(dynamic_weight, 2),
            })
            
    # 4. Rank Tasks by Score (Descending)
    scored_tasks.sort(key=lambda x: x['dynamic_weight'], reverse=True)
    
    # Assign ranking integers
    for i, task in enumerate(scored_tasks):
        task['ranking'] = i + 1
        
    return scored_tasks[0] if scored_tasks else None