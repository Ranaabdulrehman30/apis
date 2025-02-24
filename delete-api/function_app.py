import azure.functions as func
import logging
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
import os
import re
from typing import Optional, Tuple

app = func.FunctionApp()

def get_file_names(url: str, file_type: str = "html") -> Tuple[str, str]:
    """Get filenames based on URL and file type.
    
    Args:
        url (str): URL of the page
        file_type (str): Type of files to handle ("html" or "pdf")
    
    Returns:
        Tuple[str, str]: Tuple containing (primary_filename, json_filename)
    """
    # Remove protocol and split by slashes
    clean_url = url.replace('https://', '').replace('http://', '')
    
    if file_type == "html":
        # For HTML file: replace slashes with underscores and keep .gov
        html_base = clean_url.replace('/', '_')
        primary_name = f"{html_base}.html"
        
        # For JSON file: use exact format needed
        json_base = clean_url.replace('/', '_').replace('.', '').replace('-', '_')
        json_name = f"{json_base}html.json"
    else:  # PDF
        # For PDF file: similar to HTML but with .pdf extension
        pdf_base = clean_url.replace('/', '_')
        primary_name = f"{pdf_base}.pdf"
        
        # For JSON file: similar format to HTML JSONs
        json_base = clean_url.replace('/', '_').replace('.', '').replace('-', '_')
        json_name = f"{json_base}pdf.json"
    
    logging.info(f"Generated primary filename: {primary_name}")
    logging.info(f"Generated JSON filename: {json_name}")
    return primary_name, json_name

def ensure_container_exists(blob_service_client: BlobServiceClient, container_name: str) -> bool:
    """Create container if it doesn't exist or use existing one."""
    try:
        container_client = blob_service_client.get_container_client(container_name)
        try:
            # Try to get container properties to check if it exists
            container_client.get_container_properties()
            logging.info(f"Using existing container: {container_name}")
            return True
        except Exception:
            # Container doesn't exist, create it
            logging.info(f"Creating new container: {container_name}")
            blob_service_client.create_container(container_name)
            logging.info(f"Successfully created container: {container_name}")
            return True
    except Exception as e:
        logging.error(f"Error with container {container_name}: {str(e)}")
        return False

def move_blob(
    blob_service_client: BlobServiceClient,
    source_container: str,
    dest_container: str,
    blob_name: str
) -> bool:
    """Move blob from source to destination container."""
    try:
        # Add detailed logging
        logging.info(f"Attempting to move blob:")
        logging.info(f"Source container: {source_container}")
        logging.info(f"Destination container: {dest_container}")
        logging.info(f"Blob name: {blob_name}")
        
        # Get source and destination clients
        source_container_client = blob_service_client.get_container_client(source_container)
        dest_container_client = blob_service_client.get_container_client(dest_container)
        
        # Get source blob
        source_blob = source_container_client.get_blob_client(blob_name)
        
        try:
            source_properties = source_blob.get_blob_properties()
            logging.info(f"Found source blob with properties: {source_properties.name}")
        except Exception as e:
            logging.error(f"Source blob {blob_name} not found in {source_container}. Error: {str(e)}")
            return False
        
        # Get destination blob
        dest_blob = dest_container_client.get_blob_client(blob_name)
        
        # Start copy operation
        logging.info(f"Starting copy of {blob_name} to {dest_container}")
        dest_blob.start_copy_from_url(source_blob.url)
        
        # Verify copy success
        dest_properties = dest_blob.get_blob_properties()
        if dest_properties.copy.status == 'success':
            # Delete source blob after successful copy
            logging.info(f"Copy successful, deleting source blob")
            source_blob.delete_blob()
            logging.info(f"Successfully moved {blob_name} from {source_container} to {dest_container}")
            return True
        else:
            logging.error(f"Copy failed for {blob_name}. Status: {dest_properties.copy.status}")
            return False
            
    except Exception as e:
        logging.error(f"Error moving blob {blob_name}: {str(e)}")
        return False

def find_document_id(filename: str, search_client: SearchClient, file_type: str = "html") -> Optional[str]:
    """Search for a document in the index based on filename."""
    try:
        if file_type == "pdf":
            # For PDFs, search by exact file_name field
            results = search_client.search(
                search_text=f"file_name:'{filename}.pdf'",
                select=["id"],
                include_total_count=True
            )
        else:
            # For HTML files, keep existing search
            results = search_client.search(
                search_text=filename,
                select=["id"],
                include_total_count=True
            )
        
        results_list = list(results)
        
        if not results_list:
            logging.info(f"No document found with filename: {filename}")
            return None
            
        if len(results_list) > 1:
            logging.warning(f"Multiple documents found with filename: {filename}")
            
        return results_list[0]["id"]
        
    except Exception as e:
        logging.error(f"Error searching for document: {str(e)}")
        return None

def delete_document(document_id: str, search_client: SearchClient) -> bool:
    """Delete a document from the search index by its ID."""
    try:
        result = search_client.delete_documents([{"id": document_id}])
        
        if result and result[0].succeeded:
            logging.info(f"Successfully deleted document with id: {document_id}")
            return True
        else:
            error_msg = result[0].error_message if result and result[0].error_message else "Unknown error"
            logging.error(f"Failed to delete document: {error_msg}")
            return False
            
    except Exception as e:
        logging.error(f"Error deleting document: {str(e)}")
        return False

@app.function_name("DeleteFromIndex")
@app.route(route="DeleteFromIndex", auth_level=func.AuthLevel.ANONYMOUS)
async def delete_from_index(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function HTTP trigger to delete files and move them to archive."""
    try:
        # Get filename and file type from request body
        req_body = req.get_json()
        filename = req_body.get('filename')
        file_type = req_body.get('file_type', 'html').lower()  # Default to html
        
        if not filename:
            return func.HttpResponse(
                "Please provide a filename in the request body",
                status_code=400
            )
            
        if file_type not in ['html', 'pdf']:
            return func.HttpResponse(
                "File type must be either 'html' or 'pdf'",
                status_code=400
            )
            
        # Initialize clients
        search_endpoint = os.environ["SEARCH_SERVICE_ENDPOINT"]
        search_key = os.environ["SEARCH_ADMIN_KEY"]
        index_name = os.environ["SEARCH_INDEX_NAME"] if file_type == "html" else os.environ["PDF_SEARCH_INDEX_NAME"]
        
        search_credential = AzureKeyCredential(search_key)
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=search_credential
        )
        
        connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Process files and index
        operations_results = []
        
        if file_type == "html":
            # Get HTML and JSON filenames
            html_name, json_name = get_file_names(filename)
            
            # Move HTML file
            html_moved = move_blob(
                blob_service_client,
                "htmlcontent",
                "htmlcontent-archieve",
                html_name
            )
            if html_moved:
                operations_results.append("HTML file moved to archive")
            
            # Move JSON file
            json_moved = move_blob(
                blob_service_client,
                "html-jsons-gov-1",
                "jsonfiles-archieve",
                json_name
            )
            if json_moved:
                operations_results.append("JSON file moved to archive")
        else:  # PDF
            # For PDF files, just append .pdf extension
            pdf_name = f"{filename}.pdf"
            
            # Move PDF file
            pdf_moved = move_blob(
                blob_service_client,
                "evidencefiles",
                "evidencefiles-archieve",
                pdf_name
            )
            if pdf_moved:
                operations_results.append("PDF file moved to archive")
        
        # Delete from search index
        document_id = find_document_id(filename, search_client)
        if document_id and delete_document(document_id, search_client):
            operations_results.append("Document deleted from search index")
        
        if not operations_results:
            return func.HttpResponse(
                "No files found to process",
                status_code=404
            )
        
        return func.HttpResponse(
            f"Success: {', '.join(operations_results)}",
            status_code=200
        )
            
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return func.HttpResponse(
            f"Error processing request: {str(e)}",
            status_code=500
        )

#test123