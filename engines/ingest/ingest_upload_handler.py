#!/usr/bin/env python3
"""
Ingest Upload Handler v2
Handles file uploads (ZIP or single files) and establishes canonical storage layout

This is the core Lambda logic ported to the modernizeit-api project.
"""

import json
import boto3
import hashlib
import zipfile
import io
import base64
import time
import mimetypes
from datetime import datetime, timezone
from botocore.exceptions import ClientError

# Import type mapping from local module
from engines.ingest.type_mapping_templates import COBOL_TO_JAVA_TYPE_MAPPING

s3_client = boto3.client('s3')

# Constants
BUCKET_NAME = 'code-transformation-v2'
SUPPORTED_EXTENSIONS = [
    '.cbl', '.cobol', '.cob',  # COBOL
    '.cpy', '.copy',            # Copybooks
    '.jcl', '.jbc', '.job',     # JCL
    '.sql', '.ddl',             # SQL
    '.txt', '.md', '.json', '.xml', '.properties', '.yaml', '.yml',  # Config/Docs
    '.zip'                      # Archives
]


def lambda_handler(event, context):
    """
    Main handler for ingest upload
    Accepts multipart/form-data from API Gateway
    """

    try:
        print(f"Ingest upload request received: {json.dumps(event.get('requestContext', {}))}")

        # Parse multipart form data from API Gateway
        content_type = event.get('headers', {}).get('content-type', '') or event.get('headers', {}).get('Content-Type', '')
        print(f"DEBUG: Content-Type header = {content_type}")

        if 'multipart/form-data' not in content_type:
            return error_response(400, 'Content-Type must be multipart/form-data')

        # Parse form fields
        form_data = parse_multipart_form_data(event, content_type)

        # Validate required fields
        if 'file' not in form_data:
            return error_response(400, 'Missing required field: file')
        if 'scout_account_id' not in form_data:
            return error_response(400, 'Missing required field: scout_account_id')
        if 'application_name' not in form_data:
            return error_response(400, 'Missing required field: application_name')

        # Extract fields
        file_data = form_data['file']
        scout_account_id = form_data['scout_account_id']
        application_name = form_data['application_name']
        automate_flow = form_data.get('automate_flow', 'false').lower() == 'true'

        # Validate file
        if not file_data.get('content'):
            return error_response(400, 'File content is empty')

        filename = file_data.get('filename', 'uploaded_file')
        file_content = file_data['content']

        print(f"Processing upload: {filename} ({len(file_content)} bytes) for account={scout_account_id}, app={application_name}")

        # DEBUG: Check first and last bytes of file
        first_bytes = file_content[:10] if len(file_content) >= 10 else file_content
        last_bytes = file_content[-10:] if len(file_content) >= 10 else file_content
        print(f"DEBUG: File size received: {len(file_content)} bytes")
        print(f"DEBUG: First 10 bytes (hex): {first_bytes.hex()}")
        print(f"DEBUG: Last 10 bytes (hex): {last_bytes.hex()}")

        # ZIP files should start with PK (0x504B) and end with specific markers
        if filename.lower().endswith('.zip'):
            if not file_content.startswith(b'PK'):
                print(f"WARNING: ZIP file doesn't start with PK magic bytes!")
            # ZIP central directory end record starts with 0x504b0506
            if not (b'PK\x05\x06' in file_content[-100:]):
                print(f"WARNING: ZIP file missing end of central directory signature!")

        # Compute SHA-256 hash of content
        source_hash = hashlib.sha256(file_content).hexdigest()
        print(f"Source hash: {source_hash}")

        # Generate job_id
        timestamp = int(time.time())
        job_id = f"ingest_job_{scout_account_id}_{application_name}_{timestamp}_{source_hash[:8]}"

        # Define S3 paths
        base_path = f"{scout_account_id}/{application_name}"
        upload_path = f"{base_path}/shared/uploads/{source_hash}"
        catalog_path = f"{base_path}/shared/catalogs/{source_hash}"

        # Check if this content already exists
        existing = check_existing_upload(upload_path)
        if existing:
            print(f"Content already exists at {upload_path}, skipping upload")
            # Still create job metadata even for duplicate uploads
            create_job_metadata(job_id, scout_account_id, application_name, source_hash, automate_flow, base_path)

            return success_response(job_id, source_hash, base_path, upload_path, automate_flow, duplicate=True)

        # Determine if ZIP or single file
        is_zip = filename.lower().endswith('.zip')

        if is_zip:
            # Handle ZIP upload
            extracted_files = process_zip_upload(file_content, upload_path)
            print(f"Extracted {len(extracted_files)} files from ZIP")
        else:
            # Handle single file upload
            extracted_files = process_single_file_upload(file_content, filename, upload_path)
            print(f"Stored single file: {filename}")

        # Generate catalogs
        file_catalog = generate_file_catalog(extracted_files, source_hash)
        classified_catalog = generate_classified_catalog(extracted_files, source_hash)

        # Store catalogs
        store_catalog(catalog_path, 'file_catalog.json', file_catalog)
        store_catalog(catalog_path, 'classified_catalog.json', classified_catalog)

        # Generate type mappings if COBOL detected
        if classified_catalog['summary']['cobol'] > 0:
            print(f"Detected {classified_catalog['summary']['cobol']} COBOL files, generating type mapping...")
            type_mapping = generate_type_mapping('cobol', 'java', source_hash)
            if type_mapping:
                store_type_mapping(base_path, source_hash, 'cobol_to_java.json', type_mapping)

                # Store metadata
                metadata = {
                    'source_hash': source_hash,
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'mappings_created': ['cobol_to_java.json'],
                    'detected_languages': ['cobol'],
                    'cobol_file_count': classified_catalog['summary']['cobol']
                }
                store_type_mapping(base_path, source_hash, 'metadata.json', metadata)
                print(f"Type mapping generation complete")

        # Update latest pointer
        update_latest_pointer(base_path, source_hash)

        # Create job metadata
        create_job_metadata(job_id, scout_account_id, application_name, source_hash, automate_flow, base_path)

        print(f"Ingest completed successfully: {job_id}")

        return success_response(job_id, source_hash, base_path, upload_path, automate_flow)

    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}")

def parse_multipart_form_data(event, content_type):
    """
    Parse multipart/form-data from API Gateway event
    Properly handles binary file uploads without corruption
    """
    # Extract boundary from content-type
    boundary = None
    for part in content_type.split(';'):
        if 'boundary=' in part:
            boundary = part.split('boundary=')[1].strip()
            break

    if not boundary:
        raise ValueError("No boundary found in content-type")

    # Get body (may be base64 encoded)
    body = event.get('body', '')
    is_base64 = event.get('isBase64Encoded', False)

    print(f"DEBUG: isBase64Encoded = {is_base64}")
    print(f"DEBUG: body type = {type(body)}")
    print(f"DEBUG: body length (if string) = {len(body) if isinstance(body, str) else 'N/A'}")

    if is_base64:
        body = base64.b64decode(body)
    else:
        body = body.encode('utf-8') if isinstance(body, str) else body

    # Parse multipart data
    form_data = {}

    # Boundary markers with proper CRLF
    boundary_start = f'--{boundary}'.encode()
    boundary_end = f'--{boundary}--'.encode()

    # Split on boundary
    parts = body.split(boundary_start)

    for part in parts:
        if not part or part.strip() == b'' or part == b'--\r\n' or part == b'--':
            continue

        # Skip the final boundary
        if part.startswith(b'--'):
            continue

        # Split headers from content - look for double CRLF
        header_end = part.find(b'\r\n\r\n')
        if header_end == -1:
            # Try with just \n\n
            header_end = part.find(b'\n\n')
            if header_end == -1:
                continue
            headers_section = part[:header_end]
            content_start = header_end + 2
        else:
            headers_section = part[:header_end]
            content_start = header_end + 4

        # Extract content
        content = part[content_start:]

        # Remove trailing CRLF and any trailing whitespace/boundaries
        # The content ends right before the next boundary marker
        # Strip all trailing CRLFs
        while content.endswith(b'\r\n'):
            content = content[:-2]
        while content.endswith(b'\n'):
            content = content[:-1]
        while content.endswith(b'\r'):
            content = content[:-1]

        # Parse Content-Disposition header
        headers = headers_section.decode('utf-8', errors='ignore')
        field_name = None
        filename = None

        for line in headers.split('\n'):
            line = line.strip()
            if 'Content-Disposition' in line:
                # Extract field name
                if 'name="' in line:
                    name_start = line.find('name="') + 6
                    name_end = line.find('"', name_start)
                    field_name = line[name_start:name_end]

                # Extract filename if present
                if 'filename="' in line:
                    filename_start = line.find('filename="') + 10
                    filename_end = line.find('"', filename_start)
                    filename = line[filename_start:filename_end]

        if field_name:
            if filename:
                # This is a file field - keep content as raw bytes
                form_data[field_name] = {
                    'filename': filename,
                    'content': content
                }
            else:
                # This is a regular text field
                form_data[field_name] = content.decode('utf-8', errors='ignore').strip()

    return form_data

def check_existing_upload(upload_path):
    """
    Check if content with this hash already exists
    """
    try:
        s3_client.head_object(
            Bucket=BUCKET_NAME,
            Key=f"{upload_path}/extracted/"
        )
        return True
    except ClientError:
        return False

def process_zip_upload(file_content, upload_path):
    """
    Process ZIP file: store original and extract contents
    """
    # Store original ZIP
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=f"{upload_path}/uploaded_application_files.zip",
        Body=file_content,
        ContentType='application/zip'
    )

    # Extract ZIP
    extracted_files = []
    skipped_files = []

    with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
        for file_info in zf.filelist:
            if file_info.is_dir():
                continue

            filename = file_info.filename

            # Filter out junk files (Mac OS artifacts, hidden files)
            if _should_skip_file(filename):
                skipped_files.append(filename)
                continue

            file_data = zf.read(filename)

            # Store extracted file
            s3_key = f"{upload_path}/extracted/{filename}"

            # Determine content type
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=file_data,
                ContentType=content_type
            )

            extracted_files.append({
                'path': filename,
                'size': len(file_data),
                's3_key': s3_key,
                'content_type': content_type
            })

    if skipped_files:
        print(f"Skipped {len(skipped_files)} junk files: {skipped_files[:5]}{'...' if len(skipped_files) > 5 else ''}")

    return extracted_files


def _should_skip_file(filename: str) -> bool:
    """
    Check if a file should be skipped during extraction.

    Filters out:
    - Mac OS resource fork files (__MACOSX/)
    - Hidden files (starting with .)
    - .DS_Store files
    - Thumbs.db (Windows)
    """
    # Mac OS resource forks
    if '__MACOSX' in filename:
        return True

    # Get just the filename part
    basename = filename.split('/')[-1]

    # Hidden files
    if basename.startswith('.'):
        return True

    # Windows thumbnail cache
    if basename.lower() == 'thumbs.db':
        return True

    return False


def process_single_file_upload(file_content, filename, upload_path):
    """
    Process single file upload
    """
    # Check for junk files
    if _should_skip_file(filename):
        print(f"Skipped junk file: {filename}")
        return []

    # Store file in extracted/ (no need for original archive)
    s3_key = f"{upload_path}/extracted/{filename}"

    # Determine content type
    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = 'text/plain'

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=file_content,
        ContentType=content_type
    )

    return [{
        'path': filename,
        'size': len(file_content),
        's3_key': s3_key,
        'content_type': content_type
    }]

def generate_file_catalog(extracted_files, source_hash):
    """
    Generate file_catalog.json
    """
    return {
        'source_hash': source_hash,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total_files': len(extracted_files),
        'total_size': sum(f['size'] for f in extracted_files),
        'files': [
            {
                'path': f['path'],
                'size': f['size'],
                'content_type': f['content_type']
            }
            for f in extracted_files
        ]
    }

def generate_classified_catalog(extracted_files, source_hash):
    """
    Generate classified_catalog.json with basic file type classification
    """
    classifications = {
        'cobol': [],
        'copybook': [],
        'jcl': [],
        'sql': [],
        'config': [],
        'documentation': [],
        'unknown': []
    }

    for file_info in extracted_files:
        path = file_info['path']
        ext = path.lower().split('.')[-1] if '.' in path else ''

        if ext in ['cbl', 'cobol', 'cob']:
            classifications['cobol'].append(path)
        elif ext in ['cpy', 'copy']:
            classifications['copybook'].append(path)
        elif ext in ['jcl', 'jbc', 'job']:
            classifications['jcl'].append(path)
        elif ext in ['sql', 'ddl']:
            classifications['sql'].append(path)
        elif ext in ['json', 'xml', 'yaml', 'yml', 'properties']:
            classifications['config'].append(path)
        elif ext in ['txt', 'md']:
            classifications['documentation'].append(path)
        else:
            classifications['unknown'].append(path)

    return {
        'source_hash': source_hash,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'classifications': classifications,
        'summary': {
            category: len(files) for category, files in classifications.items()
        }
    }

def store_catalog(catalog_path, filename, catalog_data):
    """
    Store catalog JSON to S3
    """
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=f"{catalog_path}/{filename}",
        Body=json.dumps(catalog_data, indent=2),
        ContentType='application/json'
    )

def generate_type_mapping(source_lang, target_lang, source_hash):
    """
    Generate type mapping file for detected source language
    Currently supports: COBOL to Java
    Future: C++, FORTRAN, etc.
    """
    if source_lang.lower() == 'cobol' and target_lang.lower() == 'java':
        # Create a copy of the template and add metadata
        mapping = COBOL_TO_JAVA_TYPE_MAPPING.copy()
        mapping['generated_at'] = datetime.now(timezone.utc).isoformat()
        mapping['source_hash'] = source_hash
        return mapping
    else:
        # Future: Add other language mappings here
        return None

def store_type_mapping(base_path, source_hash, filename, mapping_data):
    """
    Store type mapping to S3 in shared/type_mappings/
    """
    mapping_path = f"{base_path}/shared/type_mappings/{source_hash}"

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=f"{mapping_path}/{filename}",
        Body=json.dumps(mapping_data, indent=2),
        ContentType='application/json'
    )

    print(f"Type mapping stored: {mapping_path}/{filename}")

def update_latest_pointer(base_path, source_hash):
    """
    Update latest pointer to current source_hash
    """
    pointer_data = {
        'source_hash': source_hash,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=f"{base_path}/shared/uploads/latest.json",
        Body=json.dumps(pointer_data, indent=2),
        ContentType='application/json'
    )

def create_job_metadata(job_id, scout_account_id, application_name, source_hash, automate_flow, base_path):
    """
    Create job_info.json and status.json for this ingest job
    """
    job_path = f"{base_path}/ingest/jobs/{job_id}"

    # job_info.json
    job_info = {
        'job_id': job_id,
        'function': 'ingest',
        'scout_account_id': scout_account_id,
        'application_name': application_name,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_hash': source_hash,
        'inputs': {
            'automate_flow': automate_flow
        }
    }

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=f"{job_path}/job_info.json",
        Body=json.dumps(job_info, indent=2),
        ContentType='application/json'
    )

    # status.json
    status_info = {
        'state': 'completed',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'progress': 1.0,
        'message': 'Ingest completed successfully'
    }

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=f"{job_path}/status.json",
        Body=json.dumps(status_info, indent=2),
        ContentType='application/json'
    )

def success_response(job_id, source_hash, base_path, upload_path, automate_flow, duplicate=False):
    """
    Return success response
    """
    return {
        'statusCode': 201 if not duplicate else 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'job_id': job_id,
            'source_hash': source_hash,
            'duplicate': duplicate,
            'paths': {
                'upload_root': f"s3://{BUCKET_NAME}/{upload_path}/",
                'extracted': f"s3://{BUCKET_NAME}/{upload_path}/extracted/",
                'catalogs': f"s3://{BUCKET_NAME}/{base_path}/shared/catalogs/{source_hash}/",
                'latest_pointer': f"s3://{BUCKET_NAME}/{base_path}/shared/uploads/latest.json"
            },
            'automate_flow': automate_flow,
            'next': [
                'POST /discovery/jobs',
                'POST /code_analyze/jobs',
                'POST /transform/jobs'
            ] if not automate_flow else []
        }, indent=2)
    }

def error_response(status_code, message):
    """
    Return error response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message
        })
    }


def local_ingest_handler(event, context=None):
    """
    Local entrypoint for Ingest v2 engine.

    Expects event in the DOC-280 / v2 format:

        {
            "nodeId": "...",
            "nodeType": "lambda.local.ingest.upload",
            "inputs": {...},
            "workflowContext": {
                "scout_account_id": "...",
                "application_name": "...",
                "zip_file_path": "...",
                "working_folder": "...",
                "generate_type_mappings": bool,
                "source_lang": "cobol",
                "target_lang": "java",
                "source_hash": "..."
            },
            "config": {...}
        }

    This handler:
    1. Reads fields from workflowContext
    2. Opens the ZIP file from zip_file_path
    3. Processes using the same helpers as lambda_handler
    4. Returns a JSON-serializable dict
    """
    print("\n==================== LOCAL INGEST HANDLER EVENT ====================")
    try:
        print(json.dumps(event, indent=2))
    except:
        print(event)
    print("====================================================================\n")

    try:
        print(f"Local ingest handler invoked")

        # Extract context
        ctx = event.get('workflowContext', {})

        # Required fields
        zip_path = ctx.get('zip_file_path')
        scout_account_id = ctx.get('scout_account_id')
        application_name = ctx.get('application_name')

        if not zip_path:
            return error_response(400, 'Missing required field: zip_file_path in workflowContext')
        if not scout_account_id:
            return error_response(400, 'Missing required field: scout_account_id in workflowContext')
        if not application_name:
            return error_response(400, 'Missing required field: application_name in workflowContext')

        # Optional fields
        generate_type_mappings = ctx.get('generate_type_mappings', False)
        source_lang = ctx.get('source_lang', 'cobol')
        target_lang = ctx.get('target_lang', 'java')
        automate_flow = False  # Not used in local mode

        print(f"Processing local upload for account={scout_account_id}, app={application_name}")
        print(f"ZIP path: {zip_path}")
        print(f"Generate type mappings: {generate_type_mappings}")

        # Read ZIP file from local path
        with open(zip_path, 'rb') as f:
            file_content = f.read()

        print(f"Read {len(file_content)} bytes from ZIP file")

        # Compute or use provided source_hash
        source_hash = ctx.get('source_hash')
        if not source_hash:
            source_hash = hashlib.sha256(file_content).hexdigest()

        print(f"Source hash: {source_hash}")

        # Generate job_id
        timestamp = int(time.time())
        job_id = ctx.get('job_id') or f"ingest_job_{scout_account_id}_{application_name}_{timestamp}_{source_hash[:8]}"

        # Define S3 paths (will be redirected to local filesystem by LocalLambdaExecutor)
        base_path = f"{scout_account_id}/{application_name}"
        upload_path = f"{base_path}/shared/uploads/{source_hash}"
        catalog_path = f"{base_path}/shared/catalogs/{source_hash}"

        # Check if this content already exists
        existing = check_existing_upload(upload_path)
        if existing:
            print(f"Content already exists at {upload_path}, skipping upload")
            create_job_metadata(job_id, scout_account_id, application_name, source_hash, automate_flow, base_path)
            return success_response(job_id, source_hash, base_path, upload_path, automate_flow, duplicate=True)

        # Process ZIP file
        extracted_files = process_zip_upload(file_content, upload_path)
        print(f"Extracted {len(extracted_files)} files from ZIP")

        # Generate catalogs
        file_catalog = generate_file_catalog(extracted_files, source_hash)
        classified_catalog = generate_classified_catalog(extracted_files, source_hash)

        # Store catalogs
        store_catalog(catalog_path, 'file_catalog.json', file_catalog)
        store_catalog(catalog_path, 'classified_catalog.json', classified_catalog)

        # Generate type mappings if requested and COBOL detected
        if generate_type_mappings and classified_catalog['summary']['cobol'] > 0:
            print(f"Detected {classified_catalog['summary']['cobol']} COBOL files, generating type mapping...")
            type_mapping = generate_type_mapping(source_lang, target_lang, source_hash)
            if type_mapping:
                mapping_filename = f"{source_lang}_to_{target_lang}.json"
                store_type_mapping(base_path, source_hash, mapping_filename, type_mapping)

                # Store metadata
                metadata = {
                    'source_hash': source_hash,
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'mappings_created': [mapping_filename],
                    'detected_languages': [source_lang],
                    'cobol_file_count': classified_catalog['summary']['cobol']
                }
                store_type_mapping(base_path, source_hash, 'metadata.json', metadata)
                print(f"Type mapping generation complete")

        # Update latest pointer
        update_latest_pointer(base_path, source_hash)

        # Create job metadata
        create_job_metadata(job_id, scout_account_id, application_name, source_hash, automate_flow, base_path)

        print(f"Local ingest completed successfully: {job_id}")

        # Return success response
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'job_id': job_id,
                'source_hash': source_hash,
                'duplicate': False,
                'file_count': len(extracted_files),
                'files_processed': len(extracted_files),
                'paths': {
                    'upload_root': f"s3://{BUCKET_NAME}/{upload_path}/",
                    'extracted': f"s3://{BUCKET_NAME}/{upload_path}/extracted/",
                    'catalogs': f"s3://{BUCKET_NAME}/{catalog_path}/"
                },
                'summary': classified_catalog['summary']
            }, indent=2)
        }

    except FileNotFoundError as e:
        print(f"File not found: {str(e)}")
        return error_response(404, f"ZIP file not found: {str(e)}")
    except Exception as e:
        print(f"Error in local ingest handler: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}")
