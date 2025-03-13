# AmeriCorp AI Search APIs

This repository contains a collection of Azure Functions for managing and interacting with Azure Cognitive Search indexes. These functions handle operations such as uploading content (HTML, PDF, JSON), deleting content, and performing semantic searches.

## Repository Structure

```
├── README.md
├── src/               # Contains all Azure Function code
│   ├── BlobUpload/
│   ├── UploadHtmlBody/
│   ├── azure-html-search/
│   ├── azure-pdf-search/
│   ├── delete-api/
│   ├── delete-api-function/
│   ├── html-json/
│   ├── json-to-index/
│   ├── pdf-indexer-function/
│   └── semantic-search/
├── get_az_cred.ps1    # PowerShell script for Azure credentials
└── get_az_cred.sh     # Bash script for Azure credentials
```

Each function in the `/src/` directory is an independent Azure Function with its own configuration. See the [src/README.md](./src/README.md) file for detailed information about each function.

## Overview of Functions

The repository includes several Azure Functions that perform different operations:

- **delete-api-function**: Deletes documents from Azure Cognitive Search indexes
- **pdf-indexer-function**: Indexes PDF documents in Azure Cognitive Search
- **azure-html-search**: Searches HTML content in Azure Cognitive Search
- **azure-pdf-search**: Searches PDF content in Azure Cognitive Search
- **semantic-search**: Performs semantic searches against the indexes
- **BlobUpload**: Uploads documents to Azure Blob Storage
- **UploadHtmlBody**: Uploads HTML content for indexing
- **html-json**: Converts HTML documents to JSON format
- **json-to-index**: Uploads JSON data to search index

## Prerequisites

1. Azure subscription
2. Azure CLI installed
3. Azure Functions Core Tools installed

## Global Deployment Instructions

### Login to Azure

```bash
az login
```

### Create a Function App

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

### Configure Application Settings

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

### Disable Authentication (if needed)

```bash
az webapp auth update --name <function-app-name> \
                     --resource-group <resource-group-name> \
                     --enabled false
```

### Restart Function App

```bash
az functionapp restart --name <function-app-name> \
                      --resource-group <resource-group-name>
```

### Configure CORS (if needed)

```bash
az functionapp cors add --name <function-app-name> \
                       --resource-group <resource-group-name> \
                       --allowed-origins "<origin>"
```

## Security Considerations

- Protect your admin keys
- Consider implementing proper authentication for production use
- Restrict CORS to specific origins in production
- Remove any sensitive information from source code before committing

## Contributing

Please follow standard Git practices when contributing to this repository:

1. Create a branch for your changes
2. Make your changes
3. Submit a pull request
4. Wait for review and approval