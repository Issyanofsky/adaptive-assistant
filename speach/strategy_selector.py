
from datetime import datetime

class StrategySelector:
    def __init__(self, db_conn, redis_conn):
        self.db = db_conn
        self.redis = redis_conn
        
    def calculate_strategy_fatigue(self, last_used: datetime, current_fatigue: float) -> float:
        """Applies a decay to the fatigue if the strategy hasn't been used in a while."""
        if not last_used:
            return 0.0
            
        # If it hasn't been used in 1 hour, reduce fatigue by 0.5
        hours_since_used = (datetime.now() - last_used).total_seconds() / 3600
        decay = hours_since_used * 0.5
        
        return max(0.0, current_fatigue - decay)

    def select_best_strategy(self, user_id: str) -> dict:
        """Queries strategies and selects the winner based on weight and fatigue."""
        cur = self.db.cursor()
        
        # Fetch all available strategies
        cur.execute("""
            SELECT name, base_weight, fatigue, per_user_effectiveness, last_used 
            FROM strategies
        """)
        strategies = cur.fetchall()
        
        best_strategy = "neutral"
        highest_score = 0.0
        
        for strategy in strategies:
            name, base_weight, current_fatigue, per_user_effectiveness, last_used = strategy
            
            # Apply fatigue decay
            fatigue = self.calculate_strategy_fatigue(last_used, current_fatigue)
            
            # Get specific user effectiveness (if it exists)
            user_prefs = per_user_effectiveness if per_user_effectiveness else {}
            effectiveness = user_prefs.get(user_id, 1.0) # default multiplier is 1.0
            
            # Formula: Score = (Base Weight * Effectiveness) - Fatigue
            strategy_score = (base_weight * effectiveness) - fatigue
            
            if strategy_score > highest_score:
                highest_score = strategy_score
                best_strategy = name
                
        return {"strategy": best_strategy, "weight": round(highest_score, 2)}

    def record_strategy_usage(self, strategy_name: str):
        """Increases fatigue and updates last_used timestamp."""
        cur = self.db.cursor()
        cur.execute("""
            UPDATE strategies 
            SET fatigue = fatigue + 0.3, last_used = NOW()
            WHERE name = %s
        """, (strategy_name,))
        self.db.commit()

