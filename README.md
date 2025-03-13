# AmeriCorp AI Search APIs

This repository contains a collection of Azure Functions for managing and interacting with Azure Cognitive Search indexes. These functions handle operations such as uploading content (HTML, PDF, JSON), deleting content, and performing semantic searches.

## Overview of Functions

The repository includes several Azure Functions that perform different operations:

- **delete-api-function**: Deletes documents from Azure Cognitive Search indexes
- **pdf-indexer-function**: Indexes PDF documents in Azure Cognitive Search
- **azure-html-search**: Searches HTML content in Azure Cognitive Search
- **azure-pdf-search**: Searches PDF content in Azure Cognitive Search
- **semantic-search**: Performs semantic searches against the indexes

## Environment Variables

The functions use the following environment variables:

```
AZURE_STORAGE_CONNECTION_STRING - Connection string for Azure Storage
SEARCH_SERVICE_ENDPOINT - URL of the Azure Cognitive Search service
SEARCH_INDEX_NAME - Name of the primary HTML search index
PDF_SEARCH_INDEX_NAME - Name of the PDF search index
SEARCH_ADMIN_KEY - Admin key for Azure Cognitive Search service
```

## Python Code Overview

### Delete API Function

The delete function removes documents from Azure Cognitive Search indexes based on specified criteria:

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

### PDF Indexer Function

The PDF indexer uploads and indexes PDF documents:

```python
import azure.functions as func
import logging
import os
import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Get file from request
        file_data = req.get_body()
        filename = req.params.get('filename')
        
        # Upload to blob storage
        blob_service_client = BlobServiceClient.from_connection_string(
            os.environ['AZURE_STORAGE_CONNECTION_STRING']
        )
        container_client = blob_service_client.get_container_client("pdfs")
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(file_data, overwrite=True)
        
        # Extract text and index in search service
        # (Code for PDF text extraction and indexing)
        
        return func.HttpResponse(
            json.dumps({"status": "success", "message": "PDF indexed successfully"}),
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

### Search Functions

The search functions execute queries against Azure Cognitive Search indexes:

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

## Deployment Instructions

### Prerequisites

1. Azure subscription
2. Azure CLI installed
3. Azure Functions Core Tools installed

### Deployment Steps

1. **Login to Azure**
   ```bash
   az login
   ```

2. **Create a Function App**
   ```bash
   az functionapp create --name <function-app-name> \
                         --storage-account <storage-account-name> \
                         --resource-group <resource-group-name> \
                         --consumption-plan-location <location> \
                         --runtime python \
                         --runtime-version 3.9 \
                         --functions-version 4 \
                         --os-type linux
   ```

3. **Configure Application Settings**
   ```bash
   az functionapp config appsettings set --name <function-app-name> \
                                         --resource-group <resource-group-name> \
                                         --settings \
   AZURE_STORAGE_CONNECTION_STRING="<storage-connection-string>" \
   SEARCH_SERVICE_ENDPOINT="<search-service-endpoint>" \
   SEARCH_INDEX_NAME="<html-index-name>" \
   PDF_SEARCH_INDEX_NAME="<pdf-index-name>" \
   SEARCH_ADMIN_KEY="<search-admin-key>" \
   AzureFunctionsJobHost__extensions__http__routePrefix="api"
   ```

4. **Disable Authentication (if needed)**
   ```bash
   az webapp auth update --name <function-app-name> \
                         --resource-group <resource-group-name> \
                         --enabled false
   ```

5. **Deploy Function Code**
   
   Navigate to your function directory and run:
   ```bash
   func azure functionapp publish <function-app-name>
   ```

6. **Restart Function App**
   ```bash
   az functionapp restart --name <function-app-name> \
                          --resource-group <resource-group-name>
   ```

7. **Configure CORS (if needed)**
   ```bash
   az functionapp cors add --name <function-app-name> \
                           --resource-group <resource-group-name> \
                           --allowed-origins "<origin>"
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

## Security Considerations

- Protect your admin keys
- Consider implementing proper authentication for production use
- Restrict CORS to specific origins in production

## Troubleshooting

- Check Application Insights logs for detailed error information
- Verify environment variables are set correctly
- Use the Azure Functions Core Tools for local debugging

## Contributing

Please follow standard Git practices when contributing to this repository:

1. Create a branch for your changes
2. Make your changes
3. Submit a pull request
4. Wait for review and approval