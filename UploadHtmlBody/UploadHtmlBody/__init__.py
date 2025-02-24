import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError
import os
from urllib.parse import unquote
import json

def extract_filename_from_url(url: str) -> str:
    """Remove https:// and replace slashes with underscores"""
    # Remove any trailing slashes
    url = url.rstrip('/')
    
    # Remove https:// or http:// from the URL
    if url.startswith('https://'):
        url = url[8:]  # Remove 'https://'
    elif url.startswith('http://'):
        url = url[7:]  # Remove 'http://'
    
    # Replace slashes with underscores
    url = url.replace('/', '_')
    
    # Ensure the URL ends with .html
    if not url.endswith('.html'):
        url = url + '.html'
    
    # Replace encoded characters in URL if any (like %2C) with their actual characters
    url = unquote(url)
        
    return url

def handle_upload(url: str, body: str) -> tuple[dict, int]:
    """Handle the upload process and return response data and status code"""
    # Extract filename from URL
    filename = extract_filename_from_url(url)
    original_url = url  # Keep original URL for metadata
    logging.info(f'Extracted filename: {filename}')
    
    # Get connection string from environment variable
    connect_str = os.environ['AzureWebJobsStorage']
    
    # Create the BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    
    # Get container client
    container_name = "htmlcontent"
    container_client = blob_service_client.get_container_client(container_name)
    
    # Create container if it doesn't exist
    try:
        container_client.get_container_properties()
    except Exception:
        container_client = blob_service_client.create_container(container_name)

    # Create blob client
    blob_client = container_client.get_blob_client(filename)
    
    # Upload the blob
    content_settings = ContentSettings(
        content_type='text/html',
        content_disposition=f'inline; filename="{filename}"'
    )
    
    blob_client.upload_blob(
        data=body,
        overwrite=True,
        content_settings=content_settings,
        metadata={'original_url': original_url}
    )
    
    logging.info(f'Successfully uploaded blob: {filename}')
    
    return {
        "message": "HTML content uploaded successfully",
        "container": container_name,
        "filename": filename,
        "originalUrl": original_url
    }, 202

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for HTML upload.')
    
    try:
        url = None
        body = None
        content_type = req.headers.get('content-type', '').lower()
        
        # Log request details for debugging
        logging.info(f"Request method: {req.method}")
        logging.info(f"Content type: {content_type}")
        
        # Handle different content types
        if 'application/json' in content_type:
            try:
                data = req.get_json()
                url = data.get('url')
                body = data.get('body')
                logging.info("Successfully parsed JSON data")
            except ValueError:
                logging.error("Failed to parse JSON data")
                
        elif 'multipart/form-data' in content_type:
            try:
                form = req.form
                url = form.get('url')
                body = form.get('body')
                logging.info("Successfully parsed form data")
            except Exception as e:
                logging.error(f"Failed to parse form data: {str(e)}")
                
        elif 'application/x-www-form-urlencoded' in content_type:
            try:
                form = req.form
                url = form.get('url')
                body = form.get('body')
                logging.info("Successfully parsed urlencoded form data")
            except Exception as e:
                logging.error(f"Failed to parse urlencoded form data: {str(e)}")
        
        # Log received data
        logging.info(f"Received URL: {url}")
        logging.info(f"Received body length: {len(body) if body else 0}")
        
        if not url or not body:
            return func.HttpResponse(
                json.dumps({
                    "error": "Both 'url' and 'body' are required",
                    "received_content_type": content_type,
                    "received_url": bool(url),
                    "received_body": bool(body)
                }),
                mimetype="application/json",
                status_code=400
            )

        # Process the upload
        response_data, status_code = handle_upload(url, body)
        
        return func.HttpResponse(
            body=json.dumps(response_data),
            mimetype="application/json",
            status_code=status_code
        )
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "error": str(e),
                "type": "Internal server error"
            }),
            mimetype="application/json",
            status_code=500
        )