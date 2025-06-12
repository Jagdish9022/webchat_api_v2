import re
import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from langchain.text_splitter import RecursiveCharacterTextSplitter
from urllib.parse import urljoin, urlparse
import warnings
import logging
from typing import Dict, List, Set
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import time
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global rate limiting
RATE_LIMIT = 2  # requests per second
last_request_time = 0

# Thread pool for CPU-bound operations
thread_pool = ThreadPoolExecutor(max_workers=4)

async def rate_limit():
    """Implement rate limiting to avoid overwhelming servers."""
    global last_request_time
    current_time = time.time()
    time_since_last = current_time - last_request_time
    if time_since_last < 1.0 / RATE_LIMIT:
        await asyncio.sleep(1.0 / RATE_LIMIT - time_since_last)
    last_request_time = time.time()

async def scrape_url_async(session: aiohttp.ClientSession, url: str) -> str:
    """Scrape content from a single URL asynchronously."""
    try:
        await rate_limit()
        async with session.get(url, timeout=ClientTimeout(total=10)) as response:
            if response.status == 200:
                return await response.text()
            return ""
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return ""

def clean_text(html: str) -> str:
    """Clean HTML and extract meaningful text."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract text from meaningful tags
        texts = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "span"])
        clean_texts = []
        
        for element in texts:
            text = element.get_text(strip=True)
            if text and len(text) > 10:  # Filter out very short texts
                clean_texts.append(text)
        
        return "\n".join(clean_texts)
    except Exception as e:
        logger.error(f"Failed to clean text: {e}")
        return ""

async def crawl_website_async(start_url: str, max_pages: int = None) -> Dict[str, str]:
    """Crawl a website starting from the given URL asynchronously."""
    visited: Set[str] = set()
    data: Dict[str, str] = {}
    urls_to_visit: List[str] = [start_url]
    
    # Configure aiohttp session with custom headers and connection pooling
    connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
    timeout = ClientTimeout(total=30)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    async with aiohttp.ClientSession(headers=headers, connector=connector, timeout=timeout) as session:
        while urls_to_visit:
            # If max_pages is set and we've reached the limit, stop
            if max_pages is not None and len(visited) >= max_pages:
                break
                
            # Process URLs in batches for better concurrency
            batch_size = min(5, len(urls_to_visit))  # Process up to 5 URLs concurrently
            current_batch = urls_to_visit[:batch_size]
            urls_to_visit = urls_to_visit[batch_size:]
            
            # Create tasks for the current batch
            tasks = []
            for url in current_batch:
                if url not in visited:
                    tasks.append(scrape_url_async(session, url))
            
            # Wait for all tasks in the batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for url, html in zip(current_batch, results):
                if isinstance(html, Exception):
                    logger.error(f"Error crawling {url}: {html}")
                    continue
                    
                if not html:
                    continue
                    
                visited.add(url)
                data[url] = html
                
                # Extract links for further crawling
                soup = BeautifulSoup(html, "html.parser")
                for link in soup.find_all("a", href=True):
                    full_url = urljoin(url, link["href"])
                    
                    # Only crawl links from the same domain
                    if (urlparse(full_url).netloc == urlparse(start_url).netloc 
                        and full_url not in visited 
                        and full_url not in urls_to_visit):
                        
                        # Skip certain file types and fragments
                        if not should_skip_url(full_url):
                            urls_to_visit.append(full_url)
    
    logger.info(f"Crawling completed. Total pages crawled: {len(data)}")
    return data

async def crawl_website(start_url: str, max_pages: int = None) -> Dict[str, str]:
    """Async wrapper for website crawling."""
    return await crawl_website_async(start_url, max_pages)

def should_skip_url(url: str) -> bool:
    """Check if URL should be skipped based on file extension or other criteria."""
    skip_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar', '.exe', '.dmg', '.mp4', '.mp3', '.avi']
    skip_patterns = ['#', 'mailto:', 'tel:', 'javascript:', 'ftp://']
    
    url_lower = url.lower()
    
    # Skip if it has a file extension we don't want
    for ext in skip_extensions:
        if url_lower.endswith(ext):
            return True
    
    # Skip if it matches certain patterns
    for pattern in skip_patterns:
        if pattern in url_lower:
            return True
    
    return False

def preprocess_text(text: str) -> str:
    """Preprocess text to ensure it's clean and properly formatted."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s.,!?-]', '', text)
    # Ensure proper spacing around punctuation
    text = re.sub(r'\s+([.,!?])', r'\1', text)
    return text.strip()

def create_chunks(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Create overlapping chunks from text with fixed size."""
    if not text:
        return []
    
    # Split text into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        sentence_size = len(sentence)
        
        if current_size + sentence_size > chunk_size and current_chunk:
            # Join current chunk and add to chunks
            chunk_text = ' '.join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text)
            
            # Start new chunk with overlap
            overlap_sentences = []
            overlap_size = 0
            for s in reversed(current_chunk):
                if overlap_size + len(s) <= overlap:
                    overlap_sentences.insert(0, s)
                    overlap_size += len(s)
                else:
                    break
            
            current_chunk = overlap_sentences
            current_size = overlap_size
        
        current_chunk.append(sentence)
        current_size += sentence_size
    
    # Add the last chunk if it exists
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        if chunk_text.strip():
            chunks.append(chunk_text)
    
    return chunks