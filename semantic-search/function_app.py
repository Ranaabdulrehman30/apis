import azure.functions as func
import logging
import json
import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import openai
from typing import List
import requests

app = func.FunctionApp()

class SearchService:
    def __init__(self):
        # Initialize credentials and endpoints
        self.search_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
        
        # Initialize search client for semantic search
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.search_key)
        )
        
        # Configure OpenAI
        openai.api_type = "azure"
        openai.api_key = os.getenv("AZURE_OPENAI_KEY")
        openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
        openai.api_version = "2023-05-15"

    def get_first_url(self, urls):
        """Get the first URL from a list of URLs."""
        if isinstance(urls, list) and urls:
            return urls[0]
        return ""

    def get_embedding(self, text: str) -> List[float]:
        """Generate embeddings for the given text."""
        response = openai.Embedding.create(
            input=text,
            engine=os.getenv("AZURE_OPENAI_DEPLOYMENT")
        )
        return response['data'][0]['embedding']

    def semantic_search(self, query: str, k: int = 50) -> List[dict]:
        """Perform semantic search using Azure Cognitive Search."""
        try:
            results = self.search_client.search(
                search_text=query,
                query_type='semantic',
                semantic_configuration_name='my-semantic-config',
                select=['title', 'summary', 'content', 'domain', 'embedded_urls'],
                query_caption='extractive',
                top=k
            )
            
            search_results = []
            for result in results:
                search_result = {
                    "title": result.get("title", ""),
                    "summary": result.get("summary", ""),
                    "domain": result.get("domain", ""),
                    "url": self.get_first_url(result.get("embedded_urls")),
                    "score": result.get("@search.reranker_score", 0)
                }

                # Add captions if available
                captions = result.get("@search.captions", [])
                if captions:
                    caption = captions[0]
                    search_result["caption"] = caption.highlights if caption.highlights else caption.text

                search_results.append(search_result)
            
            return search_results

        except Exception as e:
            logging.error(f"Error in semantic_search: {str(e)}")
            raise

    def vector_search(self, query: str, k: int = 50) -> List[dict]:
        """Perform vector search using the embedded query."""
        try:
            # Get the vector embedding for the query
            vector_query = self.get_embedding(query)
            
            # Construct the search URL
            search_url = f"{self.search_endpoint}/indexes/{self.index_name}/docs/search?api-version=2023-11-01"
            
            # Prepare the headers
            headers = {
                'Content-Type': 'application/json',
                'api-key': self.search_key
            }
            
            # Prepare the request body
            body = {
                "search": "*",
                "vectorQueries": [
                    {
                        "kind": "vector",
                        "k": k,
                        "fields": "content_vector",
                        "vector": vector_query
                    }
                ]
            }
            
            # Make the request
            response = requests.post(search_url, headers=headers, json=body)
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Parse the results
            search_results = []
            results = response.json()
            
            if 'value' in results:
                for result in results['value']:
                    search_results.append({
                        "title": result.get("title", ""),
                        "summary": result.get("summary", ""),
                        "content": result.get("content", ""),
                        "domain": result.get("domain", ""),
                        "url": self.get_first_url(result.get("embedded_urls"))
                    })
            
            return search_results

        except Exception as e:
            logging.error(f"Error in vector_search: {str(e)}")
            raise

@app.route(route="search", auth_level=func.AuthLevel.ANONYMOUS)
async def search(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # Parse request body
        req_body = req.get_json()
        query = req_body.get('query')
        search_type = req_body.get('type', 'vector')  # Default to vector search if not specified
        
        if not query:
            return func.HttpResponse(
                json.dumps({"error": "No query provided in request body"}),
                mimetype="application/json",
                status_code=400
            )

        # Initialize search service
        search_service = SearchService()
        
        # Perform search based on type
        if search_type.lower() == 'semantic':
            results = search_service.semantic_search(query)
        else:
            results = search_service.vector_search(query)
        
        # Return results
        return func.HttpResponse(
            json.dumps({
                "results": results,
                "count": len(results)
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )
