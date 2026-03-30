
import psycopg2

class QAHandler:
    def __init__(self, db_conn):
        self.db = db_conn

    def search_knowledge_base(self, user_id: str, query_topic: str) -> str:
        """
        Queries PostgreSQL context tables.
        Checks Local Context first. Falls back to Web Context.
        """
        cur = self.db.cursor()
        
        # 1. Search Local Context First
        cur.execute("""
            SELECT content, confidence 
            FROM local_context 
            WHERE user_id = %s AND content ILIKE %s 
            ORDER BY confidence DESC LIMIT 1
        """, (user_id, f'%{query_topic}%'))
        
        local_result = cur.fetchone()
        
        if local_result and local_result[1] >= 0.7: # set Threshold for data - if its confidence higher then....
            return local_result[0]
            
        # 2. Fallback to Web Context if local is missing or low confidence
        cur.execute("""
            SELECT content 
            FROM web_context 
            WHERE user_id = %s AND content ILIKE %s 
            ORDER BY confidence DESC LIMIT 1
        """, (user_id, f'%{query_topic}%'))
        
        web_result = cur.fetchone()
        
        if web_result:
            return web_result[0]
            
        # 3. Ultimate Fallback
        return "אין לי מספיק מידע במערכת כדי לענות על השאלה הזו כרגע."