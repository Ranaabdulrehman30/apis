import logging
import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import json
import time
import re
import os
from typing import List, Dict, Any

def sanitize_key(key: str) -> str:
    """Sanitize document key to meet Azure Search requirements."""
    if not key:
        return f"doc-{int(time.time())}"
    if key.startswith('_'):
        key = 'doc' + key
    key = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
    return key

def parse_array_field(value) -> List[str]:
    """Convert a value to a list of strings."""
    if not value:
        return []
    if isinstance(value, str):
        if ';' in value:
            return [item.strip() for item in value.split(';') if item.strip()]
        return [value.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if item]
    return []

def clean_content(content):
    """Remove header, footer, navigation and other non-essential webpage elements."""
    # Remove header section
    content = re.sub(r'^.*?Welcome to the AmeriCorps Evidence Exchange', 
                    'Welcome to the AmeriCorps Evidence Exchange', 
                    content, flags=re.DOTALL)
    
    # Remove footer section
    content = re.sub(r'Back to main content.*$', '', content, flags=re.DOTALL)
    
    # Remove navigation elements
    content = re.sub(r'menu block (one|two|three).*?\n', '', content)
    
    # Remove breadcrumb navigation
    content = re.sub(r'Breadcrumb.*?\n', '', content)
    
    # Remove tertiary scroll bars
    content = re.sub(r'<div class="scroll.*?</div>', '', content, flags=re.DOTALL)
    
    # Clean up extra whitespace
    content = re.sub(r'\s+', ' ', content).strip()
    
    return content

def transform_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Transform raw document into the correct format for Azure Search."""
    content = str(doc.get('content', ''))
    
    # Clean the content before processing
    content = clean_content(content)
    
    if len(content.encode('utf-8')) > 32000:
        content = content[:32000]
        
    # Log the input document
    logging.info(f"Processing document with id: {doc.get('id', '')}")

    transformed_doc = {
        'id': sanitize_key(doc.get('id', '')),
        'content': content,
        'url': str(doc.get('url', '')),
        'title': str(doc.get('title', '')),
        'title2': "",
        'published_date': "",
        'changed_date': "",
        'embedded_urls': parse_array_field(doc.get('embedded_urls', [])),
        'programs': parse_array_field(doc.get('programs', [])),
        'focus_population': parse_array_field(doc.get('focus_population', [])),
        'ages_studied': parse_array_field(doc.get('ages_studied', [])),
        'resource_type': str(doc.get('resource_type', '')),
        'domain': str(doc.get('domain', '')),
        'subdomain_1': str(doc.get('subdomain_1', '')),
        'subdomain_2': str(doc.get('subdomain_2', '')),
        'subdomain_3': str(doc.get('subdomain_3', '')),
        'pdf_urls': parse_array_field(doc.get('pdf_urls', [])),
        'topic': str(doc.get('topic', '')),
        'year': str(doc.get('year', '')),
        'Status': str(doc.get('Status', '')),
        'CFDA_number': str(doc.get('CFDA_number', '')),
        'summary': str(doc.get('summary', ''))
    }
    return transformed_doc

def move_blob_to_success_container(blob_name: str, source_container: str) -> bool:
    """Move blob to successful-jsons container after successful processing."""
    try:
        # Get the connection string from environment variable
        connect_str = os.environ['AzureWebJobsStorage']
        
        # Create BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        
        # Get source container and blob
        source_container_client = blob_service_client.get_container_client(source_container)
        source_blob = source_container_client.get_blob_client(blob_name)

        # Check if source blob exists
        if not source_blob.exists():
            logging.error(f"Source blob {blob_name} does not exist")
            return False
        
        # Target container name
        target_container_name = "successful-jsons"
        
        # Create target container if it doesn't exist
        target_container_client = blob_service_client.get_container_client(target_container_name)
        try:
            target_container_client.create_container()
            logging.info(f"Created new container: {target_container_name}")
        except Exception as e:
            if "ContainerAlreadyExists" not in str(e):
                raise
            
        # Get target blob
        target_blob = target_container_client.get_blob_client(blob_name)
        
        # Start copy operation
        source_blob_url = source_blob.url
        target_blob.start_copy_from_url(source_blob_url)
        
        # Wait for copy to complete
        props = target_blob.get_blob_properties()
        while props.copy.status == 'pending':
            time.sleep(1)
            props = target_blob.get_blob_properties()
            
        # Check if copy was successful
        if props.copy.status == 'success':
            # Delete source blob
            source_blob.delete_blob()
            logging.info(f"Successfully moved {blob_name} to {target_container_name} container")
            return True
        else:
            logging.error(f"Copy operation failed with status: {props.copy.status}")
            return False
            
    except Exception as e:
        logging.error(f"Error moving blob {blob_name}: {str(e)}")
        return False

def process_blob(blob: func.InputStream, filename: str, search_client: SearchClient, source_container: str) -> bool:
    """Process a single blob and update the search index"""
    try:
        content = blob.read().decode('utf-8')
        doc = json.loads(content)
        
        transformed_doc = transform_document(doc)
        documents = [transformed_doc]
        
        logging.info(f"Sending document to index: {json.dumps(documents)}")
        
        result = search_client.merge_or_upload_documents(documents=documents)
        
        if result and result[0].succeeded:
            logging.info(f"Successfully processed document with id: {transformed_doc['id']}")
            
            # Move the blob to successful-jsons container
            if move_blob_to_success_container(filename, source_container):
                logging.info(f"Successfully moved {filename} to successful-jsons container")
            else:
                logging.warning(f"Failed to move {filename} to successful-jsons container")
                
            return True
        else:
            error_msg = result[0].error_message if result and result[0].error_message else "Unknown error"
            logging.error(f"Failed to process document: {error_msg}")
            return False
        
    except Exception as e:
        logging.error(f"Error processing file {filename}: {str(e)}")
        return False

def main(myblob: func.InputStream):
    """Azure Function blob trigger to process single file"""
    try:
        # Get the container name from the blob path
        container_name = myblob.name.split('/')[0]
        blob_name = myblob.name.split('/')[-1]
        
        logging.info(f"Python blob trigger function processing blob:\nName: {blob_name}\nSize: {myblob.length} bytes")
        
        if not blob_name.lower().endswith('.json'):
            logging.info(f"Skipping non-JSON file: {blob_name}")
            return
        
        # Get configuration from environment variables
        search_endpoint = os.environ["SEARCH_SERVICE_ENDPOINT"]
        search_key = os.environ["SEARCH_ADMIN_KEY"]
        index_name = os.environ["SEARCH_INDEX_NAME"]
        
        search_credential = AzureKeyCredential(search_key)
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=search_credential
        )
        
        success = process_blob(myblob, blob_name, search_client, container_name)
        
        if success:
            logging.info(f"Successfully indexed file: {blob_name}")
        else:
            logging.error(f"Failed to index file: {blob_name}")
            
    except Exception as e:
        logging.error(f"Error in blob trigger function: {str(e)}")
        raise