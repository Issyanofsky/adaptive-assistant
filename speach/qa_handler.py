import asyncio
import logging
import psycopg2
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

class WebSearchRetriever:
    def __init__(self, max_search_results: int = 2):
        self.max_results = max_search_results

    def _search_and_extract(self, query: str) -> list:
        """
        Queries DuckDuckGo and returns snippets and URLs directly.
        No Playwright needed, so it never crashes on Windows!
        """
        results_list = []
        try:
            with DDGS() as ddgs:
                # This fetches search results including the text snippet and the URL
                results = ddgs.text(query, max_results=self.max_results)
                
                for r in results:
                    if 'body' in r and 'href' in r:
                        results_list.append({
                            "content": r['body'].strip(),
                            "source": r['href']
                        })
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo: {e}")
            
        return results_list

    async def retrieve_web_context(self, query_topic: str) -> list:
        """
        Wraps the synchronous search in an executor so it doesn't block FastAPI.
        """
        loop = asyncio.get_running_loop()
        # Run the scraping in a background thread
        results = await loop.run_in_executor(None, self._search_and_extract, query_topic)
        return results


class QAHandler:
    def __init__(self, db_conn):
        self.db = db_conn
        self.web_retriever = WebSearchRetriever(max_search_results=2)

    async def search_knowledge_base(self, user_id: str, query_topic: str) -> str:
        """
        Queries PostgreSQL context tables.
        Falls back to live web scraping if database yields nothing.
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
        
        if local_result and local_result[1] >= 0.7:
            cur.close()
            return local_result[0]
            
        # 2. Fallback to Database Web Context
        cur.execute("""
            SELECT content 
            FROM web_context 
            WHERE user_id = %s AND content ILIKE %s 
            ORDER BY confidence DESC LIMIT 1
        """, (user_id, f'%{query_topic}%'))
        
        web_result = cur.fetchone()
        
        if web_result:
            cur.close()
            return web_result[0]
            
        # 3. Ultimate Fallback: Execute real-time Web Search Retriever
        print(f"No DB data found. Scraping live web for: {query_topic}")
        live_web_results = await self.web_retriever.retrieve_web_context(query_topic)
        
        if not live_web_results:
            cur.close()
            return "אין לי מספיק מידע במערכת כדי לענות על השאלה הזו כרגע."
            
        # 4. Save results back to your database and prepare context for LLM
        combined_markdown_context = ""
        
        for item in live_web_results:
            content = item["content"]
            source = item["source"]
            
            combined_markdown_context += f"\n\n--- Source: {source} ---\n{content}"
            
            try:
                cur.execute("""
                    INSERT INTO web_context (context, source, confidence, product_relevance)
                    VALUES (%s, %s, %s, %s)
                """, (content, source, 1.0, False))
                
                self.db.commit() 
                print(f"Successfully cached search result from: {source}")
            except Exception as e:
                self.db.rollback() 
                logger.error(f"Failed to insert web context for {source}: {e}")

        cur.close()
        
        # 5. Build the prompt for the Aya model
        system_instruction = (
            "You are an expert AI assistant. Answer the user's question. "
            "You are provided with real-time extracted data from web searches below. "
            "Prioritize the facts found in this live web data over your training knowledge "
            "if they are more recent or highly specific."
        )
        
        live_search_prompt = f"""
{system_instruction}

Live Web Data found for this topic:
{combined_markdown_context.strip()}

User Question: {query_topic}
"""
        return live_search_prompt