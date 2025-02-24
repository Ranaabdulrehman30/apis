import os
import json
import logging
import re
import azure.functions as func
from typing import List, Dict
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

app = func.FunctionApp()

def get_search_context(text: str, search_text: str, context_chars: int = 300) -> str:
    """Returns context around where the search term was found. zia added comment to test pipeline v1"""
    if not text or not search_text:
        return ""
    
    text_str = str(text) if text is not None else ""
    clean_text = re.sub(r'<[^>]+>', ' ', text_str)
    clean_text = ' '.join(clean_text.split())
    
    search_terms = search_text.lower().split()
    text_lower = clean_text.lower()
    
    best_pos = -1
    for term in search_terms:
        pos = text_lower.find(term)
        if pos != -1:
            best_pos = pos
            break
    
    if best_pos == -1:
        return clean_text[:500] + "..."
        
    start = max(0, best_pos - context_chars)
    end = min(len(clean_text), best_pos + context_chars)
    
    snippet = clean_text[start:end].strip()
    
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(clean_text):
        snippet = f"{snippet}..."
        
    return snippet

def search_single_index(
    search_text: str,
    search_client: SearchClient,
    index_name: str,
    max_results: int = 200
) -> List[Dict]:
    """
    Search content field in index and return results.
    """
    try:
        logging.info(f"Searching content field in index '{index_name}' for: {search_text}")

        # Remove the field specification from the search query
        response = list(search_client.search(
            search_text=search_text,  # Changed from f"content:{search_text}"
            select=["content", "file_name", "url", "id"],
            query_type="simple",  # Changed from "full" to "simple"
            top=max_results
        ))
        
        logging.info(f"Found {len(response)} results")

        results = []
        for result in response:
            content = get_search_context(result.get("content", ""), search_text)
            
            # Transform URL if needed
            url = result.get("url", "")
            if url.startswith('https://americorpevidencestore.blob.core.windows.net/evidencefiles/'):
                url = url.replace(
                    'https://americorpevidencestore.blob.core.windows.net/evidencefiles/',
                    'https://americorps.gov/sites/default/files/evidenceexchange/'
                )
            
            result_dict = {
                "content": content,
                "file_name": result.get("file_name", ""),
                "url": url,
                "id": result.get("id", "")
            }
            results.append(result_dict)

        return results
    except Exception as e:
        logging.error(f"Search error: {str(e)}", exc_info=True)
        return []

@app.route(route="search_pdf", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def search_function(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function HTTP trigger handler.
    """
    try:
        req_body = req.get_json()
        search_text = req_body.get("search_text", "")

        if not search_text:
            return func.HttpResponse(
                json.dumps({"error": "search_text is required"}),
                status_code=400,
                mimetype="application/json"
            )

        # Initialize clients
        search_endpoint = os.getenv("SEARCH_SERVICE_ENDPOINT")
        search_key = os.getenv("SEARCH_SERVICE_API_KEY")
        index_name = os.getenv("SECONDARY_SEARCH_INDEX_NAME", "pdf-search-index")  # Updated default index name
        
        if not all([search_endpoint, search_key, index_name]):
            raise ValueError("Missing required environment variables: SEARCH_ENDPOINT, SEARCH_KEY, or INDEX_NAME")

        logging.info(f"Using index: '{index_name}'")

        # Initialize search client
        search_credential = AzureKeyCredential(search_key)
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=search_credential
        )

        # Perform search
        results = search_single_index(
            search_text=search_text,
            search_client=search_client,
            index_name=index_name,
            max_results=200
        )

        return func.HttpResponse(
            json.dumps(results, ensure_ascii=False, indent=2),
            mimetype="application/json"
        )
        
    except ValueError as ve:
        logging.error(f"Configuration error: {str(ve)}")
        return func.HttpResponse(
            json.dumps({"error": str(ve)}),
            status_code=400,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Search error: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
