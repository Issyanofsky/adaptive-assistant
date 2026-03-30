
import asyncio
import logging
from duckduckgo_search import DDGS
from crawl4ai import AsyncWebCrawler

# Setting up basic logging to see what's happening in your state machine terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSearchRetriever:
    def __init__(self, max_search_results: int = 2):
        """
        Initializes the search retriever.
        :param max_search_results: How many websites to scrape per query.
                                   Keep this low (1-2) to maintain fast response times.
        """
        self.max_results = max_search_results

    def _get_urls(self, query: str) -> list:
        """Helper to fetch URLs from DuckDuckGo without a key."""
        try:
            logger.info(f"Fetching search results for: {query}")
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=self.max_results)
                urls = [r['href'] for r in results if 'href' in r]
                logger.info(f"Found {len(urls)} URLs.")
                return urls
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo: {e}")
            return []

    async def retrieve_web_context(self, query_topic: str) -> str:
        """
        The main async function to call.
        Searches the web and returns clean markdown text of the top pages.
        """
        # 1. Get the URLs
        # Running the synchronous DDGS in an executor keeps it from blocking your async loop
        loop = asyncio.get_running_loop()
        urls = await loop.run_in_executor(None, self._get_urls, query_topic)
        
        if not urls:
            return "No recent web data could be found for this topic."

        # 2. Scrape the pages using Crawl4AI
        combined_markdown_context = ""
        
        try:
            async with AsyncWebCrawler() as crawler:
                for url in urls:
                    logger.info(f"Scraping live content from: {url}")
                    try:
                        # Adding a 10-second timeout so a slow site doesn't freeze the AI
                        result = await asyncio.wait_for(
                            crawler.arun(url=url), 
                            timeout=10.0
                        )
                        
                        if result.success and result.markdown:
                            combined_markdown_context += f"\n\n--- Source: {url} ---\n{result.markdown}"
                        else:
                            logger.warning(f"Failed to scrape or extract text from {url}")
                            
                    except asyncio.TimeoutError:
                        logger.warning(f"Skipping {url} due to a connection timeout.")
                    except Exception as e:
                        logger.error(f"Error scraping {url}: {e}")
                        
        except Exception as e:
            logger.error(f"Crawl4AI failed to initialize: {e}")
            
        return combined_markdown_context.strip()