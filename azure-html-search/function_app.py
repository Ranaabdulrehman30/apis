import azure.functions as func
import logging
import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from typing import Optional, List, Union, Dict
import os
from dataclasses import dataclass
import re

# Initialize the function app
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@dataclass
class SearchRequest:
    search_text: str
    programs: Optional[Union[List[str], str]] = None
    ages_studied: Optional[Union[List[str], str]] = None
    focus_population: Optional[str] = None
    domain: Optional[str] = None
    subdomain_1: Optional[str] = None  # Added subdomain_1
    subdomain_2: Optional[str] = None  # Added subdomain_2
    subdomain_3: Optional[str] = None  # Added subdomain_3
    resource_type: Optional[str] = None 
    topic: Optional[str] = None      # Added topic
    year: Optional[str] = None 
    Status: Optional[str] = None      
    CFDA_number: Optional[str] = None   
    summary: Optional[str] = None 
    title: Optional[str] = None 
    published_date: Optional[str] = None 
    changed_date: Optional[str] = None 


def get_first_n_lines(text: str, n: int = 1) -> str:
    """Safely get first n lines from text content."""
    if not text:
        return ""
    # Convert to string if not already a string
    text_str = str(text) if text is not None else ""
    lines = text_str.split('\n')
    return '\n'.join(lines[:n]).strip()

def get_search_context(text: str, search_text: str, context_chars: int = 150) -> str:
    """
    Returns context around where the search term was found.
    Args:
        text (str): The full content text to search in
        search_text (str): The search term to look for
        context_chars (int): Number of characters to include before and after the match
    Returns:
        str: The context snippet with the search term and surrounding text
    """
    if not text or not search_text:
        logging.info(f"Empty text or search_text: text='{text}', search_text='{search_text}'")
        return ""
    
    # Convert to string and clean HTML
    text_str = str(text) if text is not None else ""
    
    # First remove navigation and header/footer content
    text_str = re.sub(r'<nav[^>]*>.*?</nav>', ' ', text_str, flags=re.DOTALL | re.IGNORECASE)
    text_str = re.sub(r'<header[^>]*>.*?</header>', ' ', text_str, flags=re.DOTALL | re.IGNORECASE)
    text_str = re.sub(r'<footer[^>]*>.*?</footer>', ' ', text_str, flags=re.DOTALL | re.IGNORECASE)
    text_str = re.sub(r'<menu[^>]*>.*?</menu>', ' ', text_str, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove remaining HTML tags using simple regex
    clean_text = re.sub(r'<[^>]+>', ' ', text_str)
    # Remove extra whitespace
    clean_text = ' '.join(clean_text.split())
    
    # Log the cleaned text for debugging
    logging.info(f"Cleaned text length: {len(clean_text)}")
    logging.info(f"First 100 chars of cleaned text: {clean_text[:100]}")
    
    # Find the position of the search term (case insensitive)
    search_text_lower = search_text.lower()
    text_lower = clean_text.lower()
    
    position = text_lower.find(search_text_lower)
    if position == -1:
        # Try finding partial matches
        words = search_text_lower.split()
        for word in words:
            if len(word) > 3:  # Only search for words longer than 3 characters
                position = text_lower.find(word)
                if position != -1:
                    break
                
    if position == -1:
        logging.info(f"No match found for search_text: '{search_text}' in content")
        return ""
        
    # Calculate the context window
    start = max(0, position - context_chars)
    end = min(len(clean_text), position + len(search_text) + context_chars)
    
    # Get the context snippet
    snippet = clean_text[start:end].strip()
    
    # Add ellipsis if we're not at the start/end of the text
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(clean_text):
        snippet = f"{snippet}..."
    
    logging.info(f"Found context snippet: {snippet}")
    return snippet

def get_first_url(embedded_urls: Union[str, List[str], None]) -> Optional[str]:
    """Safely get first URL from embedded_urls."""
    if not embedded_urls:
        return None
    if isinstance(embedded_urls, list):
        return embedded_urls[0] if embedded_urls else None
    if isinstance(embedded_urls, str):
        urls = embedded_urls.split(';')
        return urls[0] if urls else None
    return None

def ensure_list(value: Union[List[str], str, None]) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return value

def has_filters(search_request: SearchRequest) -> bool:
    """Check if any filters are present in the search request."""
    return any([
        search_request.programs,
        search_request.ages_studied,
        search_request.focus_population,
        search_request.domain,
        search_request.subdomain_1,  # Added subdomain checks
        search_request.subdomain_2,
        search_request.subdomain_3,
        search_request.resource_type,
        search_request.topic,
        search_request.year,
        search_request.Status,
        search_request.CFDA_number,
        search_request.summary,
        search_request.title,
        search_request.published_date,
        search_request.changed_date,
    ])

def build_filter_string(search_request: SearchRequest) -> Optional[str]:
    filters = []
    
    if search_request.programs:
        programs = ensure_list(search_request.programs)
        programs_filter = " or ".join(f"programs/any(p: p eq '{prog}')" for prog in programs)
        filters.append(f"({programs_filter})")
        logging.info(f"Programs filter: {programs_filter}")
        
    if search_request.ages_studied:
        ages = ensure_list(search_request.ages_studied)
        ages_filter = " or ".join(f"ages_studied/any(a: a eq '{age}')" for age in ages)
        filters.append(f"({ages_filter})")
        logging.info(f"Ages filter: {ages_filter}")
    
    if search_request.focus_population:
        population_filter = f"focus_population/any(f: f eq '{search_request.focus_population}')"
        filters.append(f"({population_filter})")
        logging.info(f"Focus population filter: {population_filter}")
    
    if search_request.domain:
        filters.append(f"domain eq '{search_request.domain}'")
        logging.info(f"Domain filter: domain eq '{search_request.domain}'")
    
    # Add subdomain filters
    if search_request.subdomain_1:
        filters.append(f"subdomain_1 eq '{search_request.subdomain_1}'")
        logging.info(f"Subdomain 1 filter: subdomain_1 eq '{search_request.subdomain_1}'")
    
    if search_request.subdomain_2:
        filters.append(f"subdomain_2 eq '{search_request.subdomain_2}'")
        logging.info(f"Subdomain 2 filter: subdomain_2 eq '{search_request.subdomain_2}'")
    
    if search_request.subdomain_3:
        filters.append(f"subdomain_3 eq '{search_request.subdomain_3}'")
        logging.info(f"Subdomain 3 filter: subdomain_3 eq '{search_request.subdomain_3}'")

    if search_request.resource_type:
        filters.append(f"resource_type eq '{search_request.resource_type}'")
        logging.info(f"Resource type filter: resource_type eq '{search_request.resource_type}'")

    if search_request.topic:
        filters.append(f"topic eq '{search_request.topic}'")
        logging.info(f"Topic filter: topic eq '{search_request.topic}'")

    if search_request.year:
        filters.append(f"year eq '{search_request.year}'")
        logging.info(f"Year filter: year eq '{search_request.year}'")
    
    if search_request.Status:
        filters.append(f"Status eq '{search_request.Status}'")
        logging.info(f"Status filter: Status eq '{search_request.Status}'")

    if search_request.CFDA_number:
        filters.append(f"CFDA_number eq '{search_request.CFDA_number}'")
        logging.info(f"CFDA_number filter: CFDA_number eq '{search_request.CFDA_number}'")

    if search_request.title:
            filters.append(f"title eq '{search_request.title}'")
            logging.info(f"title filter: title eq '{search_request.title}'")

    if search_request.published_date:
            filters.append(f"published_date eq '{search_request.published_date}'")
            logging.info(f"published_date filter: published_date eq '{search_request.published_date}'")

    if search_request.changed_date:
            filters.append(f"changed_date eq '{search_request.changed_date}'")
            logging.info(f"changed_date filter: changed_date eq '{search_request.changed_date}'")

    final_filter = " and ".join(filters) if filters else None
    logging.info(f"Final filter string: {final_filter}")
    return final_filter

def extract_pdf_filename(pdf_url: str) -> str:
    """
    Extract filename from PDF URL.
    Example: https://americorps.gov/sites/default/files/evidenceexchange/MinnesotaAllianceWithYouth.20AC220660.Report-Revised_508_1.pdf
    Returns: MinnesotaAllianceWithYouth.20AC220660.Report-Revised_508_1.pdf
    """
    try:
        return pdf_url.split('/')[-1]
    except:
        return ""

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

        # Simple search approach without field specification
        response = list(search_client.search(
            search_text=search_text,
            select=["content", "file_name", "url", "id"],
            query_type="simple",
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
            
            results.append({
                "content": content,
                "file_name": result.get("file_name", ""),
                "url": url,
                "id": result.get("id", ""),
                "score": result.get('@search.score', 0)
            })

        return sorted(results, key=lambda x: x['score'], reverse=True)

    except Exception as e:
        logging.error(f"Search error: {str(e)}", exc_info=True)
        return []

def extract_pdf_stem(pdf_url: str) -> str:
    """
    Extract filename without extension from PDF URL, handling URL encoding.
    """
    try:
        from urllib.parse import unquote
        # Get the filename from the URL
        filename = pdf_url.split('/')[-1]
        # URL decode the filename
        decoded_filename = unquote(filename)
        # Remove the extension
        stem = decoded_filename.rsplit('.', 1)[0]
        logging.info(f"Extracted PDF stem: {stem} from URL: {pdf_url}")
        return stem
    except Exception as e:
        logging.error(f"Error extracting PDF stem from URL {pdf_url}: {str(e)}")
        return ""

def normalize_string(s: str) -> str:
    """
    Normalize string by removing special characters and extra spaces.
    """
    import re
    # Replace special characters with spaces
    s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s)
    # Replace multiple spaces with single space
    s = re.sub(r'\s+', ' ', s)
    # Strip and lowercase
    return s.strip().lower()

def check_pdf_in_titles(pdf_stem: str, titles: list) -> bool:
    """
    Check if PDF stem matches any title, using normalized comparison.
    """
    if not pdf_stem:
        return False
        
    normalized_pdf = normalize_string(pdf_stem)
    logging.info(f"Normalized PDF stem: {normalized_pdf}")
    
    for title in titles:
        normalized_title = normalize_string(title)
        logging.info(f"Checking against normalized title: {normalized_title}")
        if normalized_pdf == normalized_title:
            logging.info(f"Found match between '{pdf_stem}' and '{title}'")
            return True
    return False

def filter_pdf_urls(pdf_urls: List[str]) -> List[str]:
    """Filter out common policy PDFs and return only relevant ones."""
    if not pdf_urls:
        return []
        
    excluded_pdfs = [
        "Whistleblower_Rights_Employees_OGC",
        "Whistleblower_Rights_and_Remedies_Contractors_Grantees_OGC"
    ]
    
    return [
        url for url in pdf_urls 
        if not any(excluded in url for excluded in excluded_pdfs)
    ]

def extract_final_path_segment(url: str) -> str:
    """Extract just the final path segment (filename) from either type of URL"""
    try:
        # Split by '/' and get last part
        parts = url.split('/')
        filename = parts[-1]
        
        # URL decode
        from urllib.parse import unquote
        filename = unquote(filename)
        
        return filename
    except Exception as e:
        logging.error(f"Error extracting filename from {url}: {str(e)}")
        return ""

def normalize_for_comparison(text: str) -> str:
    """
    Normalize text for comparison by removing special characters and standardizing format.
    
    Args:
        text (str): Text to normalize
        
    Returns:
        str: Normalized text
    """
    import re
    from urllib.parse import unquote
    
    try:
        # Double decode to handle potential double encoding
        text = unquote(unquote(text))
        
        # Remove .pdf extension
        text = text.replace('.pdf', '')
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace special characters and whitespace with single space
        text = re.sub(r'[^a-z0-9]+', ' ', text)
        
        # Normalize spaces and trim
        text = ' '.join(text.split())
        
        return text.strip()
    except Exception as e:
        logging.error(f"Error normalizing text: {str(e)}")
        return ""

def check_filename_match(primary_filename: str, secondary_filename: str) -> bool:
    """
    Check if two filenames match after normalization.
    
    Args:
        primary_filename (str): First filename to compare
        secondary_filename (str): Second filename to compare
        
    Returns:
        bool: True if filenames match, False otherwise
    """
    try:
        # Normalize both filenames
        norm_primary = normalize_for_comparison(primary_filename)
        norm_secondary = normalize_for_comparison(secondary_filename)
        
        logging.info(f"Normalized primary: {norm_primary}")
        logging.info(f"Normalized secondary: {norm_secondary}")
        
        # Extract significant terms (more than 3 chars)
        primary_terms = set(term for term in norm_primary.split() if len(term) > 3)
        secondary_terms = set(term for term in norm_secondary.split() if len(term) > 3)
        
        # Find common terms
        common_terms = primary_terms.intersection(secondary_terms)
        
        # Calculate similarity score
        total_terms = len(primary_terms.union(secondary_terms))
        if total_terms == 0:
            return False
            
        similarity = len(common_terms) / total_terms
        
        # Return true if similarity is above threshold (e.g., 0.5 means 50% of terms match)
        return similarity >= 0.5
        
    except Exception as e:
        logging.error(f"Error comparing filenames: {str(e)}")
        return False

@app.function_name(name="search")  # Add explicit function name
@app.route(route="search", auth_level=func.AuthLevel.ANONYMOUS)  
def search_function(req: func.HttpRequest) -> func.HttpResponse:
    try:
        logging.info("Received search request")
        request_body = req.get_json()
        
        search_text = request_body.get('search_text', '')
        search_request = SearchRequest(
            search_text=search_text,
            programs=request_body.get('programs'),
            ages_studied=request_body.get('ages_studied'),
            focus_population=request_body.get('focus_population'),
            domain=request_body.get('domain'),
            subdomain_1=request_body.get('subdomain_1'),
            subdomain_2=request_body.get('subdomain_2'),
            subdomain_3=request_body.get('subdomain_3'),
            resource_type=request_body.get('resource_type'),
            topic=request_body.get('topic'),         # Add topic
            year=request_body.get('year'),
            Status=request_body.get('Status'),        
            CFDA_number=request_body.get('CFDA_number'),
            summary=request_body.get('summary'),
            title=request_body.get('title'),
            published_date=request_body.get('published_date'),
            changed_date=request_body.get('changed_date')
        )

        # Initialize clients
        endpoint = os.environ["SEARCH_SERVICE_ENDPOINT"]
        key = os.environ["SEARCH_SERVICE_API_KEY"]
        primary_index_name = os.environ["SEARCH_INDEX_NAME"]
        secondary_index_name = os.environ.get("SECONDARY_SEARCH_INDEX_NAME", "pdf-search-index")

        credential = AzureKeyCredential(key)
        primary_client = SearchClient(endpoint=endpoint, index_name=primary_index_name, credential=credential)
        secondary_client = SearchClient(endpoint=endpoint, index_name=secondary_index_name, credential=credential)
        MAX_RESULTS = 1000
        # Build filter string
        filter_string = build_filter_string(search_request)
        
        # Execute primary search
        primary_results = list(primary_client.search(
            search_text=search_text if search_text else "*",
            filter=filter_string,
            select=[
                "content", 
                "embedded_urls", 
                "programs", 
                "ages_studied", 
                "focus_population",
                "domain",
                "subdomain_1",
                "subdomain_2",
                "subdomain_3",
                "resource_type",
                "pdf_urls",
                "title",
                "topic",
                "year",
                "Status",
                "CFDA_number",
                "summary",
                "title",
                "published_date",
                "changed_date"
            ],
            top=MAX_RESULTS if not search_text else 150  # Use MAX_RESULTS for empty search
        ))

        # Get secondary results if search text is present
        secondary_results = None
        if search_text:
            try:
                secondary_results = search_single_index(
                    search_text,
                    secondary_client,
                    secondary_index_name,
                    max_results=20
                )
                logging.info(f"Found {len(secondary_results)} results in PDF index")
            except Exception as e:
                logging.error(f"Error getting secondary results: {str(e)}")
                secondary_results = []

        # Process results
        search_results = []
        for idx, result in enumerate(primary_results):
            try:
                filtered_result = {
                    'content': get_search_context(result.get('content', ''), search_text) if search_text else get_first_n_lines(result.get('content', '')),
                    'url': get_first_url(result.get('embedded_urls')),
                    'title': result.get('title', ''),
                    'programs': result.get('programs', []),
                    'ages_studied': result.get('ages_studied', []),
                    'focus_population': result.get('focus_population', []),
                    'domain': result.get('domain', ''),
                    'subdomain_1': result.get('subdomain_1', ''),
                    'subdomain_2': result.get('subdomain_2', ''),
                    'subdomain_3': result.get('subdomain_3', ''),
                    'resource_type': result.get('resource_type', ''),
                    'pdf_urls': filter_pdf_urls(result.get('pdf_urls', [])),
                    'found_in_pdf': "Found only in HTML",
                    'topic': result.get('topic', ''),    # Add topic
                    'year': result.get('year', ''),
                    'Status': result.get('Status', ''),
                    'CFDA_number': result.get('CFDA_number', ''),
                    'summary': result.get('summary', ''),
                    'title': result.get('title', ''),
                    'published_date': result.get('published_date', ''),
                    'changed_date': result.get('changed_date', '')
                }

                # Only perform PDF matching for first 10 results if domain is evidence-exchange
                if idx < 10 and search_text:
                    try:
                        # Get secondary results
                        secondary_results = search_single_index(
                            search_text=search_text,
                            search_client=secondary_client,
                            index_name=secondary_index_name,
                            max_results=10
                        )
                        
                        logging.info(f"Found {len(secondary_results)} results in PDF index")
                        
                        # Check only first two PDFs
                        first_two_pdfs = filtered_result['pdf_urls'][:2]
                        for pdf_url in first_two_pdfs:
                            if not pdf_url:
                                continue

                            try:
                                # Extract primary filename
                                from urllib.parse import unquote
                                primary_filename = unquote(unquote(pdf_url.split('/')[-1]))
                                primary_basename = primary_filename.rsplit('.', 1)[0].lower()
                                
                                logging.info(f"Checking primary PDF: {primary_filename}")
                                
                                # Check against secondary results
                                for sec_result in secondary_results:
                                    secondary_filename = sec_result.get('file_name', '')
                                    if not secondary_filename:
                                        continue
                                        
                                    secondary_basename = secondary_filename.rsplit('.', 1)[0].lower()
                                    
                                    logging.info(f"Comparing with: {secondary_filename}")

                                    # Compare normalized filenames
                                    if normalize_string(primary_basename) == normalize_string(secondary_basename):
                                        logging.info(f"Found matching filenames: {primary_filename} and {secondary_filename}")
                                        filtered_result['found_in_pdf'] = "Found in both HTML and PDF"
                                        filtered_result['pdf_content'] = sec_result.get('content', '')
                                        break
                                        
                                if filtered_result['found_in_pdf'] == "Found in both HTML and PDF":
                                    break

                            except Exception as e:
                                logging.error(f"Error processing PDF {pdf_url}: {str(e)}", exc_info=True)
                                continue
                                    
                    except Exception as e:
                        logging.error(f"Error in PDF matching: {str(e)}", exc_info=True)
                        filtered_result['found_in_pdf'] = "Error checking PDF"

                # Add the result if it has content
                if (filtered_result['content'] or 
                    filtered_result['url'] or 
                    filtered_result['pdf_urls']):
                    search_results.append(filtered_result)
                    
            except Exception as e:
                logging.error(f"Error processing result: {str(e)}")
                continue

        # Construct response data
        response_data = {
            "results": search_results,
            "applied_filters": {
                "programs": search_request.programs,
                "ages_studied": search_request.ages_studied,
                "focus_population": search_request.focus_population,
                "domain": search_request.domain,
                "subdomain_1": search_request.subdomain_1,
                "subdomain_2": search_request.subdomain_2,
                "subdomain_3": search_request.subdomain_3,
                "topic": search_request.topic,    # Add topic
                "year": search_request.year,
                "Status": search_request.Status,
                "CFDA_number": search_request.CFDA_number,
                "summary": search_request.summary,
                "title": search_request.title,
                "published_date": search_request.published_date,
                "changed_date": search_request.changed_date
            }
        }

        if search_text:
            response_data["total_count"] = len(search_results)

        return func.HttpResponse(
            json.dumps(response_data),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error in search function: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "error": str(e),
                "type": type(e).__name__,
                "search_text": request_body.get('search_text', '') if 'request_body' in locals() else None,
                "filter_string": filter_string if 'filter_string' in locals() else None
            }),
            mimetype="application/json",
            status_code=500
        )