import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
import os
from datetime import datetime
import json

def validate_request(req: func.HttpRequest) -> tuple[bool, str]:
    """Validate the request parameters"""
    # Check required headers
    file_name = req.headers.get('file_name')
    file_type = req.headers.get('file_type')
    
    if not file_name:
        return False, "file_name is required in headers"
    if not file_type:
        return False, "file_type is required in headers"
        
    # Validate file type format
    if not file_type.startswith('.'):
        file_type = f".{file_type}"
    
    # Validate if filename has correct extension
    if not file_name.endswith(file_type):
        return False, f"file_name must end with the specified file_type: {file_type}"
    
    return True, ""

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # Validate request
        is_valid, error_message = validate_request(req)
        if not is_valid:
            return func.HttpResponse(
                body=json.dumps({
                    "error": error_message
                }),
                mimetype="application/json",
                status_code=400
            )

        # Get request parameters
        file_name = req.headers.get('file_name')
        output_path = req.headers.get('outputPath', '')
        
        # Get the file content
        file_content = req.get_body()
        
        # Get connection string from environment variable
        connect_str = os.environ['AzureWebJobsStorage']
        
        # Create the BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        
        # Get container name - default to 'evidencefiles' if not specified in outputPath
        container_name = "evidencefiles"
        blob_path = file_name

        if output_path:
            # Remove leading/trailing slashes
            output_path = output_path.strip('/')
            
            # Check if output_path includes container name (first segment)
            path_segments = output_path.split('/')
            if len(path_segments) > 0:
                container_name = path_segments[0]
                # Reconstruct blob path without container name
                if len(path_segments) > 1:
                    blob_path = f"{'/'.join(path_segments[1:])}/{file_name}"
                else:
                    blob_path = file_name

        # Get container client
        container_client = blob_service_client.get_container_client(container_name)
        
        # Create container if it doesn't exist
        try:
            container_client.get_container_properties()
        except Exception:
            container_client = blob_service_client.create_container(container_name)
        
        # Create blob client
        blob_client = container_client.get_blob_client(blob_path)
        
        # Upload the file
        blob_client.upload_blob(file_content, overwrite=True)
        
        # Construct full path for response
        full_path = f"{container_name}/{blob_path}"
        
        # Return success response
        return func.HttpResponse(
            body=json.dumps({
                "message": f"File uploaded successfully to blob at {full_path}"
            }),
            mimetype="application/json",
            status_code=202
        )
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(
            body=json.dumps({
                "error": "An error occurred while uploading file. Please contact the administrator."
            }),
            mimetype="application/json",
            status_code=500
        )