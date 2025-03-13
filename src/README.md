# AmeriCorp AI Search APIs - Functions

This directory contains all the Azure Functions used in the AmeriCorp AI Search APIs project. Each subdirectory represents an independent Azure Function with its own configuration.

## Function Details

### delete-api-function

Deletes documents from Azure Cognitive Search indexes based on document ID.

**Key Features:**
- Accepts document ID and optional index name
- Handles response formatting and error handling
- Uses Azure Search Document client

**Sample Code:**
```python
import azure.functions as func
import json
import logging
import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Get request body
        req_body = req.get_json()
        document_id = req_body.get('document_id')
        index_name = req_body.get('index_name', os.environ['SEARCH_INDEX_NAME'])
        
        # Connect to search service
        search_client = SearchClient(
            endpoint=os.environ['SEARCH_SERVICE_ENDPOINT'],
            index_name=index_name,
            credential=AzureKeyCredential(os.environ['SEARCH_ADMIN_KEY'])
        )
        
        # Delete document
        result = search_client.delete_documents([{"id": document_id}])
        
        return func.HttpResponse(
            json.dumps({"status": "success", "result": str(result)}),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status_code=500
        )
```

### pdf-indexer-function

Uploads and indexes PDF documents in Azure Cognitive Search.

**Key Features:**
- Accepts PDF file uploads
- Stores documents in Azure Blob Storage
- Extracts text content for indexing
- Creates searchable documents in the PDF search index

### azure-html-search

Performs searches against HTML content stored in Azure Cognitive Search.

**Key Features:**
- Accepts search text as input
- Performs full-text search with highlighting
- Returns formatted search results with metadata

**Sample Code:**
```python
import azure.functions as func
import logging
import os
import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Get search parameters
        req_body = req.get_json()
        search_text = req_body.get('search_text', '')
        
        # Connect to search service
        search_client = SearchClient(
            endpoint=os.environ['SEARCH_SERVICE_ENDPOINT'],
            index_name=os.environ['SEARCH_INDEX_NAME'],
            credential=AzureKeyCredential(os.environ['SEARCH_ADMIN_KEY'])
        )
        
        # Perform search
        results = search_client.search(
            search_text=search_text,
            include_total_count=True,
            select="id,title,content,url",
            highlight_fields="content",
            highlight_pre_tag="<b>",
            highlight_post_tag="</b>"
        )
        
        # Format and return results
        search_results = []
        for result in results:
            search_results.append({
                "id": result["id"],
                "title": result["title"],
                "content": result["content"],
                "url": result["url"],
                "highlights": result.get("@search.highlights", {})
            })
            
        return func.HttpResponse(
            json.dumps({
                "status": "success", 
                "count": results.get_count(), 
                "results": search_results
            }),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status_code=500
        )
```

### azure-pdf-search

Similar to azure-html-search but specifically for searching PDF content.

### semantic-search

Performs semantic searches using Azure Cognitive Search capabilities.

**Key Features:**
- Uses semantic ranking features
- Supports natural language queries
- Returns semantically relevant results

### BlobUpload

Handles uploading documents to Azure Blob Storage.

### UploadHtmlBody

Processes and indexes HTML content for search.

### html-json

Converts HTML documents to JSON format for indexing.

### json-to-index

Uploads JSON data directly to the search index.

## Environment Variables

Each function uses some or all of the following environment variables:

```
AZURE_STORAGE_CONNECTION_STRING - Connection string for Azure Storage
SEARCH_SERVICE_ENDPOINT - URL of the Azure Cognitive Search service
SEARCH_INDEX_NAME - Name of the primary HTML search index
PDF_SEARCH_INDEX_NAME - Name of the PDF search index
SEARCH_ADMIN_KEY - Admin key for Azure Cognitive Search service
```

## Deploying Individual Functions

To deploy a specific function from this directory:

```bash
# Navigate to the function directory
cd delete-api-function

# Deploy just this function
func azure functionapp publish <function-app-name>
```

## Local Development

For local development, create a `local.settings.json` file in each function directory with content similar to:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_STORAGE_CONNECTION_STRING": "your-connection-string",
    "SEARCH_SERVICE_ENDPOINT": "your-search-endpoint",
    "SEARCH_INDEX_NAME": "your-index-name",
    "PDF_SEARCH_INDEX_NAME": "your-pdf-index-name",
    "SEARCH_ADMIN_KEY": "your-admin-key"
  }
}
```

## API Usage Examples

### Delete a Document
```bash
curl -X POST https://<function-app-name>.azurewebsites.net/api/delete \
     -H "Content-Type: application/json" \
     -d '{"document_id": "doc123", "index_name": "html-dev-index-updated-11"}'
```

### Search HTML Content
```bash
curl -X POST https://<function-app-name>.azurewebsites.net/api/search \
     -H "Content-Type: application/json" \
     -d '{"search_text": "your search query"}'
```

## Troubleshooting

- Check Application Insights logs for detailed error information
- Verify environment variables are set correctly
- Use the Azure Functions Core Tools for local debugging
- Check function.json files for routing and binding configurations