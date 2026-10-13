import re
import time
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple, Callable, Any
from llama_index.core.schema import Document
import wikipedia

logger = logging.getLogger(__name__)

class TextCleaner:
    @staticmethod
    def clean_text(raw_text: str) -> str:
        """Sanitize raw text, removing Wikipedia markup artifacts, footnotes, and excessive whitespace."""
        if not raw_text:
            return ""
        # Remove [edit] markers
        text = re.sub(r'\[edit\]', '', raw_text, flags=re.IGNORECASE)
        # Remove citation footnotes like [1], [2], [14]
        text = re.sub(r'\[\d+\]', '', text)
        # Remove multiple consecutive blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Strip trailing/leading spaces on lines
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()

# Configure user-agent for Wikipedia API requests (required by Wikimedia API policy)
WIKI_USER_AGENT = "CognitiveRAG/2.0 (Spatial 3D Vector Research Platform; contact: research@cognitiverag.internal)"
try:
    wikipedia.set_user_agent(WIKI_USER_AGENT)
except Exception:
    pass

class WikipediaLoader:
    @staticmethod
    def get_wikipedia_url(title: str) -> str:
        formatted = title.strip().replace(' ', '_')
        return f"https://en.wikipedia.org/wiki/{formatted}"

    @classmethod
    def _fetch_via_api_direct(cls, title: str) -> Optional[Dict[str, Any]]:
        """Direct fallback using Wikimedia action API with redirects and plain text extraction."""
        import requests
        headers = {'User-Agent': WIKI_USER_AGENT}
        api_url = 'https://en.wikipedia.org/w/api.php'
        
        params = {
            'action': 'query',
            'format': 'json',
            'titles': title,
            'prop': 'extracts|info|revisions',
            'explaintext': '1',
            'inprop': 'url',
            'redirects': '1',
            'rvprop': 'ids|timestamp'
        }
        try:
            r = requests.get(api_url, headers=headers, params=params, timeout=12)
            data = r.json()
            pages = data.get('query', {}).get('pages', {})
            for pid, page in pages.items():
                if pid != '-1' and page.get('extract'):
                    rev_id = ""
                    if page.get('revisions'):
                        rev_id = str(page['revisions'][0].get('revid', ''))
                    return {
                        "title": page['title'],
                        "text": page['extract'],
                        "url": page.get('fullurl', cls.get_wikipedia_url(page['title'])),
                        "page_id": pid,
                        "revision_id": rev_id
                    }
        except Exception as e:
            logger.warning("Direct wiki API error for '%s': %s", title, e)

        # Try opensearch to find closest title if direct query missed
        try:
            search_params = {
                'action': 'opensearch',
                'search': title,
                'limit': 3,
                'namespace': 0,
                'format': 'json'
            }
            sr = requests.get(api_url, headers=headers, params=search_params, timeout=10)
            sdata = sr.json()
            if len(sdata) >= 2 and sdata[1]:
                best_match = sdata[1][0]
                return cls._fetch_via_api_direct(best_match)
        except Exception:
            pass

        return None

    @classmethod
    def load_single_article(cls, article_name: str) -> Tuple[Optional[Document], str]:
        """Loads a single article safely with error handling, disambiguation, and API fallback."""
        cleaned_name = article_name.strip()
        if not cleaned_name:
            return None, "Empty title provided"

        raw_text = ""
        title = cleaned_name
        url = cls.get_wikipedia_url(cleaned_name)
        page_id = ""
        revision_id = ""

        try:
            wikipedia.set_user_agent(WIKI_USER_AGENT)
        except Exception:
            pass
            
        # Strategy 1: wikipedia Python package
        try:
            try:
                page = wikipedia.page(cleaned_name, auto_suggest=False)
                raw_text = page.content
                title = page.title
                url = page.url
                page_id = getattr(page, 'pageid', '') or ''
                revision_id = getattr(page, 'revision_id', '') or ''
            except wikipedia.exceptions.DisambiguationError as de:
                first_option = de.options[0] if de.options else cleaned_name
                logger.info("Disambiguation for '%s', resolving to '%s'", cleaned_name, first_option)
                page = wikipedia.page(first_option, auto_suggest=False)
                raw_text = page.content
                title = page.title
                url = page.url
                page_id = getattr(page, 'pageid', '') or ''
                revision_id = getattr(page, 'revision_id', '') or ''
            except (wikipedia.exceptions.PageError, Exception):
                search_results = wikipedia.search(cleaned_name, results=1)
                if search_results:
                    page = wikipedia.page(search_results[0], auto_suggest=False)
                    raw_text = page.content
                    title = page.title
                    url = page.url
                    page_id = getattr(page, 'pageid', '') or ''
                    revision_id = getattr(page, 'revision_id', '') or ''
        except Exception as e:
            logger.info("Wikipedia package missed '%s' (%s), attempting direct Wikimedia API fallback...", cleaned_name, e)

        # Strategy 2: Direct Wikimedia API fallback
        if not raw_text:
            direct = cls._fetch_via_api_direct(cleaned_name)
            if direct:
                title = direct["title"]
                raw_text = direct["text"]
                url = direct["url"]
                page_id = direct.get("page_id", "")
                revision_id = direct.get("revision_id", "")

        if not raw_text:
            return None, f"Article '{cleaned_name}' could not be found on Wikipedia"

        cleaned_text = TextCleaner.clean_text(raw_text)
        if not cleaned_text:
            return None, f"Article '{cleaned_name}' contained no readable text"

        content_hash = hashlib.sha256(cleaned_text.encode('utf-8')).hexdigest()[:32]

        doc = Document(
            text=cleaned_text,
            metadata={
                "title": title,
                "original_query": cleaned_name,
                "url": url,
                "type": "wikipedia",
                "char_count": len(cleaned_text),
                "page_id": page_id,
                "revision_id": revision_id,
                "content_hash": content_hash,
                "fetched_at": time.time()
            }
        )
        return doc, "Loaded"

class IngestionPipeline:
    """
    High-level ingestion pipeline supporting bounded concurrent article downloads,
    progress tracking, and clean text extraction.
    """
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def load_wikipedia_articles(
        self,
        article_names: List[str],
        progress_callback: Optional[Callable[[str, str, float], None]] = None
    ) -> Tuple[List[Document], Dict[str, str]]:
        """
        Loads multiple Wikipedia articles concurrently.
        progress_callback(article_name, status_message, float_ratio)
        """
        seen = set()
        unique_names = []
        for name in article_names:
            clean = name.strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                unique_names.append(clean)

        total = len(unique_names)
        results: Dict[str, Tuple[Optional[Document], str]] = {}
        completed_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_article = {
                executor.submit(WikipediaLoader.load_single_article, name): name
                for name in unique_names
            }
            
            for future in as_completed(future_to_article):
                art_name = future_to_article[future]
                completed_count += 1
                try:
                    doc, status = future.result()
                    results[art_name] = (doc, status)
                except Exception as e:
                    results[art_name] = (None, f"Error: {str(e)[:60]}")
                
                ratio = completed_count / total if total > 0 else 1.0
                if progress_callback:
                    status_text = results[art_name][1]
                    progress_callback(art_name, status_text, ratio)

        successful_docs = [res[0] for res in results.values() if res[0] is not None]
        status_map = {name: res[1] for name, res in results.items()}
        return successful_docs, status_map

    def load_custom_text(self, title: str, text: str, source_type: str = "custom") -> Document:
        """Directly ingest custom text or user documents."""
        cleaned = TextCleaner.clean_text(text)
        content_hash = hashlib.sha256(cleaned.encode('utf-8')).hexdigest()[:32]
        return Document(
            text=cleaned,
            metadata={
                "title": title.strip(),
                "url": "",
                "type": source_type,
                "char_count": len(cleaned),
                "content_hash": content_hash,
                "fetched_at": time.time()
            }
        )
