from azure.storage.blob import BlobServiceClient
import azure.functions as func
from openai import AzureOpenAI
import json
import re
import os
import urllib.parse
import traceback

app = func.FunctionApp()

def get_credentials():
    """Get Azure credentials from environment variables."""
    return {
        'storage_connection': os.environ["AzureWebJobsStorage"]
    }

def extract_url_components(url):
    """Extract components from URL and handle special cases."""
    try:
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        components = [x for x in path.split('/') if x]
        
        if not components:
            return {'domain': '', 'title': ''}
        
        result = {
            'domain': components[0],
            'title': components[-1]
        }
        
        if components[0] == 'blogs' and len(components) >= 3:
            date_component = components[1]
            date_parts = date_component.split('-')
            if len(date_parts) == 3:
                result['subdomain_1'] = date_parts[0]  # Year
                result['subdomain_2'] = date_parts[1]  # Month
                result['subdomain_3'] = date_parts[2]  # Day
                return result
        
        for i, component in enumerate(components[1:-1], 1):
            decoded_component = urllib.parse.unquote(component)
            result[f'subdomain_{i}'] = decoded_component
            
        return result
            
    except Exception as e:
        print(f"Error extracting URL components: {str(e)}")
        return {'domain': '', 'title': ''}

def find_matches(content, terms, category_name=None):
    """Find matches of terms in content with special handling for PROGRAM(S) category."""
    found_terms = []
    
    if category_name == "PROGRAM(S)":
        program_requirements = {
            "AmeriCorps Seniors": 9,
            "AmeriCorps NCCC": 3,
            "AmeriCorps State and National": 3,
            "Volunteer Generation Fund": 3,
            "AmeriCorps VISTA": 3
        }
        
        for term in terms:
            if term in program_requirements:
                count = content.count(term)
                required_count = program_requirements[term]
                if count >= required_count:
                    found_terms.append(term)
            else:
                if term in content:
                    found_terms.append(term)
    else:
        for term in terms:
            if term in content:
                found_terms.append(term)
                
    return found_terms if found_terms else []

def extract_categories(content):
    """Extract all categories from the content."""
    categories = {
        "PROGRAM(S)": [
            "Social Innovation Fund",
            "AmeriCorps NCCC",
            "AmeriCorps State and National",
            "AmeriCorps VISTA",
            "AmeriCorps Seniors",
            "Volunteer Generation Fund",
            "Office of Research and Evaluation",
            "Public Health AmeriCorps"
        ],
        "FOCUS POPULATION": [
            "Opportunity Youth",
            "Opportunity-Youth",
            "Opportunity-youth",
            "Schools",
            "Nonprofits",
            "Non-profits",
            "Non profits"
            "Tribes",
            "Veterans and Military Families",
            "Rural",
            "Suburban",
            "Urban",
            "Low-income",
            "Low income"
        ],
        "AGES STUDIED": [
            "0-5 (Early Childhood)",
            "0-5 (early childhood)",
            "0-5 (Early childhood)",
            "6-12 (Childhood)",
            "13-17 (Adolescent)",
            "18-25 (Young adult)",
            "18-25 (Young Adult)",
            "26-55 (Adult)",
            "55+ (Older adult)",
            "0-5 (Early childhood)"
        ]
    }
    
    results = {}
    for category, terms in categories.items():
        found_terms = find_matches(content, terms, category)
        results[category] = found_terms
    
    return results

def extract_embedded_urls(content):
    """Extract embedded URLs from content."""
    try:
        urls = re.findall(r'href=[\'"](https?://[^\'"]+)[\'"]', content)
        if urls:
            return [url for url in urls if not url.endswith(('.css', '.js'))]
    except Exception as e:
        print(f"Error extracting URLs: {str(e)}")
    return []

def extract_pdf_urls(content):
    """Extract PDF URLs from content."""
    try:
        pdf_matches = re.findall(r'href=[\'"](/sites/default/files/[^\'"]+\.pdf)[\'"]', content)
        pdf_urls = [f"https://americorps.gov{path}" for path in pdf_matches]
        return pdf_urls
    except Exception as e:
        print(f"Error extracting PDF URLs: {str(e)}")
        return []

def join_array_values(arr):
    """Join array values with semicolon separator."""
    if not arr:
        return ""
    return "; ".join(arr)

def extract_filename_from_url(url):
    """Extract and clean filename from URL."""
    try:
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        filename = os.path.basename(path)
        filename = filename.split('?')[0]
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '_', filename)
        return filename
    except Exception as e:
        print(f"Error extracting filename: {str(e)}")
        return ""

def save_json_to_blob(blob_service_client, output_json, filename):
    """Save JSON output to blob storage."""
    try:
        print(f"Attempting to save JSON for file: {filename}")
        container_client = blob_service_client.get_container_client("html-jsons-gov-1")
        
        try:
            print("Checking if container exists...")
            container_client.get_container_properties()
        except Exception as e:
            print(f"Container doesn't exist, creating new one. Error: {str(e)}")
            container_client.create_container()
            print("Created new container: html-jsons-gov-1")
        
        blob_client = container_client.get_blob_client(f"{filename}.json")
        json_str = json.dumps(output_json, indent=2)
        blob_client.upload_blob(json_str, overwrite=True)
        print(f"JSON saved to blob storage: {filename}.json")
        return True
        
    except Exception as e:
        print(f"Error saving JSON to blob: {str(e)}")
        print(f"Full error traceback: {traceback.format_exc()}")
        return False

def move_html_to_master_container(blob_service_client, source_container_name, blob_name):
    """Move the HTML file to the htmlcontent-master container."""
    try:
        print(f"Moving HTML file {blob_name} to htmlcontent-master container")
        
        # Get source blob
        source_container_client = blob_service_client.get_container_client(source_container_name)
        source_blob_client = source_container_client.get_blob_client(blob_name)
        
        # Create target container if it doesn't exist
        target_container_name = "htmlcontent-master"
        target_container_client = blob_service_client.get_container_client(target_container_name)
        
        try:
            target_container_client.get_container_properties()
        except Exception as e:
            print(f"Target container doesn't exist, creating new one. Error: {str(e)}")
            target_container_client.create_container()
            print(f"Created new container: {target_container_name}")
        
        # Get source blob content and properties
        blob_content = source_blob_client.download_blob().readall()
        blob_properties = source_blob_client.get_blob_properties()
        
        # Copy metadata
        metadata = blob_properties.metadata
        
        # Upload to target container
        target_blob_client = target_container_client.get_blob_client(blob_name)
        target_blob_client.upload_blob(blob_content, overwrite=True, metadata=metadata)
        print(f"Uploaded blob to {target_container_name}")
        
        # Delete from source container
        source_blob_client.delete_blob()
        print(f"Deleted blob from {source_container_name}")
        
        return True
    
    except Exception as e:
        print(f"Error moving HTML file: {str(e)}")
        print(f"Full error traceback: {traceback.format_exc()}")
        return False

async def process_file(myblob: func.InputStream, filename: str, blob_service_client):
    """Process a single file uploaded to the container."""
    try:
        print(f"Processing file: {filename}")
        source_container_name = "htmlcontent"
        
        # Get blob client and metadata
        try:
            blob_client = blob_service_client.get_blob_client(container=source_container_name, blob=filename)
            blob_properties = blob_client.get_blob_properties()
            print(f"Blob properties retrieved: {blob_properties}")
            print(f"Blob metadata: {blob_properties.metadata}")
            original_url = blob_properties.metadata.get('original_url')
            print(f"Original URL from metadata: {original_url}")
            
            if not original_url:
                print(f"Warning: Missing original_url in metadata for {filename}")
                original_url = ''
            
        except Exception as e:
            print(f"Error getting blob properties: {str(e)}")
            return False
        
        # Get blob content
        try:
            content = myblob.read().decode('utf-8')
        except Exception as e:
            print(f"Error reading blob content: {str(e)}")
            return False
        
        print("Extracting information using Azure OpenAI...")
        try:
            # Initialize Azure OpenAI client
            client = AzureOpenAI(
                api_version="2024-02-15-preview",
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_key=os.environ.get("AZURE_OPENAI_API_KEY")
            )
            
            messages = [
                {"role": "system", "content": """You are a precise content analyzer specializing in AmeriCorps content. Analyze the given content and provide the following:

                1. Extract the Status sequence:
                - Look for "Status [Open/Closed]"
                - Extract only "Open" or "Closed"

                2. Extract the CFDA sequence:
                - Look for "CFDA number [XX.XXX]"
                - Extract only the number (e.g., "94.011")

                3. Generate a 4-5 line summary that:
                - Focuses on main purpose/goal
                - Captures key initiatives/components
                - Highlights outcomes and impacts
                - Notes key requirements
                - Ignores headers and HTML markup

                4. Extract a topic from these consolidated categories:
                Education & Learning:
                - Use 'literacy education' for all literacy and tutoring programs
                - Use 'stem education' for all STEM-related education
                - Use 'college access support' for all college advising/access programs
                - Use 'early childhood education' for all pre-K and early learning
                - Use 'youth education' for general youth education programs

                Community Development:
                - Use 'community development' for general community improvement
                - Use 'urban revitalization' for urban renewal/development
                - Use 'rural development' for rural community programs

                Healthcare & Wellness:
                - Use 'healthcare access' for general healthcare programs
                - Use 'mental health support' for mental health programs
                - Use 'substance abuse prevention' for drug/alcohol programs

                Veterans Services:
                - Use 'veterans housing support' for housing programs
                - Use 'veterans employment services' for job programs
                - Use 'veterans support services' for other veterans programs

                Youth Services:
                - Use 'youth development' for general youth programs
                - Use 'youth leadership' for leadership programs
                - Use 'youth mentorship' for mentoring programs

                Senior Services:
                - Use 'senior companionship' for companion programs
                - Use 'senior support services' for general senior programs

                5. Extract the most relevant year mentioned in the content
                
                Return ONLY a JSON object like:
                {
                    "Status": "Open",
                    "CFDA_number": "94.011",
                    "summary": "4-5 line summary here...",
                    "topic": "literacy education",
                    "year": "2020"
                }"""},
                {"role": "user", "content": f"Analyze this content: {content[:4000]}"}
            ]
            
            print("Sending request to OpenAI...")
            response = client.chat.completions.create(
                messages=messages,
                model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-2"),
                max_tokens=800,
                temperature=0
            )
            print("Got response from OpenAI")
            
            if response and response.choices and len(response.choices) > 0:
                response_content = response.choices[0].message.content.strip()
                print(f"Raw response: {response_content}")
                
                try:
                    # Clean up the response by removing markdown code blocks
                    cleaned_response = response_content.replace('```json', '').replace('```', '').strip()
                    print(f"Cleaned response: {cleaned_response}")
                    
                    result = json.loads(cleaned_response)
                    status = result.get("Status", "")
                    if status == "null" or status is None:
                        status = ""
                        
                    cfda = result.get("CFDA_number", "")
                    if cfda == "null" or cfda is None:
                        cfda = ""
                        
                    summary = result.get("summary", "")
                    if summary == "null" or summary is None:
                        summary = ""
                        
                    topic = result.get("topic", "")
                    if topic == "null" or topic is None:
                        topic = ""
                        
                    year = result.get("year", "")
                    if year == "null" or year is None:
                        year = ""
                        
                except json.JSONDecodeError as je:
                    print(f"JSON parsing error: {str(je)}")
                    print(f"Failed to parse response: {response_content}")
                    status = cfda = summary = topic = year = ""
            else:
                print("No valid response from OpenAI")
                status = cfda = summary = topic = year = ""
                
        except Exception as e:
            print(f"Error in OpenAI processing: {str(e)}")
            print(f"Full error traceback: {traceback.format_exc()}")
            status = cfda = summary = topic = year = ""
        
        # Extract other components
        url_components = extract_url_components(original_url)
        categories = extract_categories(content)
        blob_url = f"https://americorpevidencestore.blob.core.windows.net/htmlcontent/{filename}"
        
        # Create output JSON
        output_json = {
            "id": extract_filename_from_url(blob_url),
            "url": original_url,
            "title": url_components.get('title', ''),
            "content": content,
            "summary": summary,
            "embedded_urls": extract_embedded_urls(content),
            "pdf_urls": extract_pdf_urls(content),
            "programs": join_array_values(categories.get("PROGRAM(S)", [])),
            "focus_population": categories.get("FOCUS POPULATION", []),
            "ages_studied": categories.get("AGES STUDIED", []),
            "resource_type": url_components.get('domain', 'others'),
            "domain": url_components.get('domain', ''),
            "subdomain_1": url_components.get('subdomain_1', ''),
            "subdomain_2": url_components.get('subdomain_2', ''),
            "subdomain_3": url_components.get('subdomain_3', ''),
            "Status": status,
            "CFDA_number": cfda,
            "topic": topic,
            "year": year
        }
        
        # Save JSON
        save_filename = extract_filename_from_url(blob_url)
        json_saved = save_json_to_blob(blob_service_client, output_json, save_filename)
        
        if json_saved:
            # If JSON saved successfully, move the HTML file to master container
            move_success = move_html_to_master_container(blob_service_client, source_container_name, filename)
            if move_success:
                print(f"Successfully moved HTML file {filename} to htmlcontent-master container")
            else:
                print(f"Failed to move HTML file {filename} to htmlcontent-master container")
        
        print(f"Successfully processed and saved: {filename}")
        return True
            
    except Exception as e:
        print(f"Error processing {filename}: {str(e)}")
        print(f"Full error traceback: {traceback.format_exc()}")
        return False

@app.function_name(name="BlobTrigger1")
@app.blob_trigger(arg_name="myblob", 
                 path="htmlcontent/{name}",
                 connection="AzureWebJobsStorage")
async def main(myblob: func.InputStream) -> None:
    """Azure Function trigger that processes uploaded files."""
    try:
        print("Function triggered - starting execution")
        # Get the blob name from the path
        blob_name = myblob.name.split('/')[-1]
        
        print(f"Python blob trigger function processed blob \n"
              f"Name: {blob_name}\n"
              f"Size: {myblob.length} bytes")
        
        # Initialize client
        print("Initializing blob service client")
        credentials = get_credentials()
        blob_service_client = BlobServiceClient.from_connection_string(
            credentials['storage_connection']
        )
        
        # Process the uploaded file
        success = await process_file(myblob, blob_name, blob_service_client)
        
        if success:
            print(f"Successfully processed file: {blob_name}")
        else:
            print(f"Failed to process file: {blob_name}")
            
    except Exception as e:
        print(f"Error in function execution: {str(e)}")
        print(f"Full error traceback: {traceback.format_exc()}")
        raise

#test