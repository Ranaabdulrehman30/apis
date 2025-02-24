import logging
import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import base64
from datetime import datetime, timezone

def get_safe_document_id(blob_name: str) -> str:
    """
    Create a safe document ID by base64 encoding the blob name.
    """
    return base64.urlsafe_b64encode(blob_name.encode('utf-8')).decode('utf-8').rstrip('=')

def main(myblob: func.InputStream, context: func.Context):
    logging.info(f"Python blob trigger function processing blob: {myblob.name}")
    
    # Get blob metadata from trigger metadata
    if hasattr(context, 'binding_data'):
        blob_created = context.binding_data.get('BlobCreated')
        if blob_created:
            created_time = datetime.fromisoformat(blob_created.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            
            # Only process files created in the last 5 minutes
            time_difference = (current_time - created_time).total_seconds() / 60
            
            if time_difference > 5:  # If file is older than 5 minutes
                logging.info(f"Skipping existing file: {myblob.name} (created {time_difference:.2f} minutes ago)")
                return
    
    # Only process PDF files
    if not myblob.name.lower().endswith('.pdf'):
        logging.info(f"Skipping non-PDF file: {myblob.name}")
        return

    # Azure Search configuration
    search_service_endpoint = os.environ["SEARCH_SERVICE_ENDPOINT"]
    search_admin_key = os.environ["SEARCH_ADMIN_KEY"]
    index_name = os.environ["PDF_SEARCH_INDEX_NAME"]

    try:
        # Initialize search client
        credential = AzureKeyCredential(search_admin_key)
        search_client = SearchClient(
            endpoint=search_service_endpoint,
            index_name=index_name,
            credential=credential
        )

        # Get metadata and create safe ID
        safe_id = get_safe_document_id(myblob.name)
        
        # Create document to index
        document = {
            'id': safe_id,
            'content': None,  # Content will be extracted by the indexer
            'file_name': myblob.name,
            'url': f"https://americorpevidencestore.blob.core.windows.net/evidencefiles/{myblob.name}"
        }

        # Upload document to index
        result = search_client.upload_documents(documents=[document])
        
        # Log the result
        for res in result:
            if res.succeeded:
                logging.info(f"New document {myblob.name} indexed successfully with ID: {safe_id}")
            else:
                logging.error(f"Failed to index document {myblob.name}: {res.error_message}")

    except Exception as e:
        logging.error(f"An error occurred while processing {myblob.name}: {str(e)}")
        raise
#test