"""
DynamoDB Backend for ModernizeIT API

This module provides DynamoDB access for the API layer.
Connects to the same table as the Portal: modernizeit-dev

Schema follows single-table design with PK/SK patterns:
- User: PK=USER#email, SK=PROFILE
- Account: PK=USER#email, SK=ACCOUNT#id
- Application: PK=ACCOUNT#id, SK=APP#id
- Workflow: PK=APP#id, SK=WORKFLOW#id
- Job: PK=WORKFLOW#id, SK=JOB#id
- Setting: PK=SETTING#scope, SK=KEY#key
"""

import boto3
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from datetime import datetime
from typing import Optional, List, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

# Table configuration
# Note: Use environment variable DYNAMODB_TABLE_NAME to override
TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'modernizeit-dev')
REGION = os.getenv('AWS_REGION', 'us-east-1')

# Log the configuration on module load
logger.info(f"DynamoDB module configured: table={TABLE_NAME}, region={REGION}")

# DynamoDB client
dynamodb_client = boto3.client('dynamodb', region_name=REGION)

# Type serializers for converting Python types to DynamoDB format
serializer = TypeSerializer()
deserializer = TypeDeserializer()


def serialize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Python dict to DynamoDB format."""
    return {k: serializer.serialize(v) for k, v in item.items() if v is not None}


def deserialize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DynamoDB format to Python dict."""
    return {k: deserializer.deserialize(v) for k, v in item.items()}


def now_iso() -> str:
    """Return current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + 'Z'


# ============================================================
# CREDENTIALS
# ============================================================

def get_credentials() -> Optional[Dict[str, str]]:
    """
    Get AWS credentials from DynamoDB global settings.

    Returns:
        dict with aws_access_key_id, aws_secret_access_key, region
        or None if not found
    """
    try:
        response = dynamodb_client.get_item(
            TableName=TABLE_NAME,
            Key={
                'PK': {'S': 'SETTING#global'},
                'SK': {'S': 'KEY#aws_credentials'}
            }
        )

        if 'Item' not in response:
            logger.warning("AWS credentials not found in DynamoDB")
            return None

        item = deserialize_item(response['Item'])

        # Value is stored as JSON string
        import json
        try:
            creds = json.loads(item['value'])
            logger.info("AWS credentials loaded from DynamoDB")
            return {
                'aws_access_key_id': creds.get('accessKeyId') or creds.get('aws_access_key_id'),
                'aws_secret_access_key': creds.get('secretAccessKey') or creds.get('aws_secret_access_key'),
                'region': creds.get('region', REGION)
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse credentials: {e}")
            return None

    except Exception as e:
        logger.error(f"Failed to get credentials from DynamoDB: {e}")
        return None


def save_credentials(aws_access_key_id: str, aws_secret_access_key: str, region: str = 'us-east-1') -> bool:
    """
    Save AWS credentials to DynamoDB global settings.

    Args:
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        region: AWS region (default: us-east-1)

    Returns:
        True if successful, False otherwise
    """
    try:
        import json

        item = {
            'PK': 'SETTING#global',
            'SK': 'KEY#aws_credentials',
            'key': 'aws_credentials',
            'value': json.dumps({
                'aws_access_key_id': aws_access_key_id,
                'aws_secret_access_key': aws_secret_access_key,
                'region': region
            }),
            'scope': 'global',
            'updated_at': now_iso()
        }

        dynamodb_client.put_item(
            TableName=TABLE_NAME,
            Item=serialize_item(item)
        )

        logger.info("AWS credentials saved to DynamoDB")
        return True

    except Exception as e:
        logger.error(f"Failed to save credentials to DynamoDB: {e}")
        return False


# ============================================================
# APPLICATIONS
# ============================================================

def get_application_by_name(account_id: str, application_name: str) -> Optional[Dict[str, Any]]:
    """
    Find application by account_id + application_name.

    Args:
        account_id: Account ID (e.g., '0U812')
        application_name: Application name (e.g., 'TimsTestApp')

    Returns:
        Application dict or None if not found
    """
    try:
        # Query all applications for this account
        response = dynamodb_client.query(
            TableName=TABLE_NAME,
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': {'S': f'ACCOUNT#{account_id}'},
                ':sk': {'S': 'APP#'}
            }
        )

        # Find application with matching name
        for item in response.get('Items', []):
            app = deserialize_item(item)
            if app.get('name') == application_name:
                logger.info(f"Found application: {app.get('application_id')}")
                return app

        logger.warning(f"Application not found: {account_id}/{application_name}")
        return None

    except Exception as e:
        logger.error(f"Failed to get application: {e}")
        return None


def create_application(account_id: str, application_name: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Create new application in DynamoDB.

    Args:
        account_id: Account ID
        application_name: Application name
        **kwargs: Additional application fields (description, source_language, etc.)

    Returns:
        Created application dict or None if failed
    """
    try:
        # Generate application ID
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        app_id = f"app_{application_name}_{timestamp}"

        item = {
            'PK': f'ACCOUNT#{account_id}',
            'SK': f'APP#{app_id}',
            'account_id': account_id,
            'application_id': app_id,
            'name': application_name,
            'description': kwargs.get('description', ''),
            'source_language': kwargs.get('source_language', 'COBOL'),
            'target_language': kwargs.get('target_language', 'Java'),
            'file_count': kwargs.get('file_count', 0),
            'upload_path': kwargs.get('upload_path'),
            'catalog_path': kwargs.get('catalog_path'),
            'project_id': kwargs.get('project_id'),
            'user_email': kwargs.get('user_email'),
            'created_at': now_iso(),
            'updated_at': now_iso()
        }

        dynamodb_client.put_item(
            TableName=TABLE_NAME,
            Item=serialize_item(item)
        )

        logger.info(f"Created application: {app_id}")
        return deserialize_item(serialize_item(item))

    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        return None


# ============================================================
# WORKFLOWS
# ============================================================

def create_workflow(application_id: str, workflow_name: str, workflow_type: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Create new workflow in DynamoDB.

    Args:
        application_id: Application ID
        workflow_name: Workflow name (e.g., 'Code Analysis V3')
        workflow_type: Workflow type (e.g., 'code_analysis_v3')
        **kwargs: Additional workflow fields (account_id, user_email, etc.)

    Returns:
        Created workflow dict or None if failed
    """
    try:
        # Generate workflow ID
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        workflow_id = f"workflow_{workflow_type}_{timestamp}"

        item = {
            'PK': f'APP#{application_id}',
            'SK': f'WORKFLOW#{workflow_id}',
            'application_id': application_id,
            'workflow_id': workflow_id,
            'name': workflow_name,
            'type': workflow_type,
            'status': kwargs.get('status', 'pending'),
            'account_id': kwargs.get('account_id'),
            'user_email': kwargs.get('user_email'),
            'created_at': now_iso(),
            'started_at': kwargs.get('started_at'),
            'completed_at': kwargs.get('completed_at'),
            'error_message': kwargs.get('error_message')
        }

        dynamodb_client.put_item(
            TableName=TABLE_NAME,
            Item=serialize_item(item)
        )

        logger.info(f"Created workflow: {workflow_id}")
        return deserialize_item(serialize_item(item))

    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        return None


def update_workflow(workflow_id: str, application_id: str, **updates) -> bool:
    """
    Update workflow fields.

    Args:
        workflow_id: Workflow ID
        application_id: Application ID (needed for PK)
        **updates: Fields to update (status, started_at, completed_at, error_message)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Build update expression
        update_expr_parts = []
        attr_values = {}

        for key, value in updates.items():
            if value is not None:
                update_expr_parts.append(f'{key} = :{key}')
                attr_values[f':{key}'] = serializer.serialize(value)

        if not update_expr_parts:
            return True

        dynamodb_client.update_item(
            TableName=TABLE_NAME,
            Key={
                'PK': {'S': f'APP#{application_id}'},
                'SK': {'S': f'WORKFLOW#{workflow_id}'}
            },
            UpdateExpression='SET ' + ', '.join(update_expr_parts),
            ExpressionAttributeValues=attr_values
        )

        logger.info(f"Updated workflow: {workflow_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to update workflow: {e}")
        return False


# ============================================================
# JOBS
# ============================================================

def save_job(job_id: str, workflow_id: str, job_type: str, **kwargs) -> bool:
    """
    Save job to DynamoDB.

    Args:
        job_id: Job ID (e.g., 'ca3_job_0U812_TestApp_20260108_abc123')
        workflow_id: Workflow ID
        job_type: Job type (e.g., 'code_analysis_v3', 'ingest')
        **kwargs: Additional job fields (status, progress, input_path, etc.)

    Returns:
        True if successful, False otherwise
    """
    try:
        item = {
            'PK': f'WORKFLOW#{workflow_id}',
            'SK': f'JOB#{job_id}',
            'workflow_id': workflow_id,
            'job_id': job_id,
            'job_type': job_type,
            'status': kwargs.get('status', 'pending'),
            'progress': kwargs.get('progress', 0),
            'total_steps': kwargs.get('total_steps', 0),
            'current_step': kwargs.get('current_step', 0),
            'input_path': kwargs.get('input_path'),
            'output_path': kwargs.get('output_path'),
            'result_data': kwargs.get('result_data'),
            'error_message': kwargs.get('error_message'),
            'account_id': kwargs.get('account_id'),
            'user_email': kwargs.get('user_email'),
            'created_at': now_iso(),
            'started_at': kwargs.get('started_at'),
            'completed_at': kwargs.get('completed_at')
        }

        dynamodb_client.put_item(
            TableName=TABLE_NAME,
            Item=serialize_item(item)
        )

        logger.info(f"Saved job: {job_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to save job: {e}")
        return False


def update_job(job_id: str, workflow_id: str, **updates) -> bool:
    """
    Update job fields.

    Args:
        job_id: Job ID
        workflow_id: Workflow ID (needed for PK)
        **updates: Fields to update (status, progress, output_path, etc.)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Build update expression
        update_expr_parts = []
        attr_values = {}

        for key, value in updates.items():
            if value is not None:
                update_expr_parts.append(f'{key} = :{key}')
                attr_values[f':{key}'] = serializer.serialize(value)

        if not update_expr_parts:
            return True

        dynamodb_client.update_item(
            TableName=TABLE_NAME,
            Key={
                'PK': {'S': f'WORKFLOW#{workflow_id}'},
                'SK': {'S': f'JOB#{job_id}'}
            },
            UpdateExpression='SET ' + ', '.join(update_expr_parts),
            ExpressionAttributeValues=attr_values
        )

        logger.info(f"Updated job: {job_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to update job: {e}")
        return False


def get_job(job_id: str, workflow_id: str) -> Optional[Dict[str, Any]]:
    """
    Get job from DynamoDB.

    Args:
        job_id: Job ID
        workflow_id: Workflow ID (needed for PK)

    Returns:
        Job dict or None if not found
    """
    try:
        response = dynamodb_client.get_item(
            TableName=TABLE_NAME,
            Key={
                'PK': {'S': f'WORKFLOW#{workflow_id}'},
                'SK': {'S': f'JOB#{job_id}'}
            }
        )

        if 'Item' not in response:
            logger.warning(f"Job not found: {job_id}")
            return None

        return deserialize_item(response['Item'])

    except Exception as e:
        logger.error(f"Failed to get job: {e}")
        return None


def list_jobs(workflow_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    List jobs for a workflow.

    Args:
        workflow_id: Workflow ID
        limit: Maximum number of jobs to return (default: 100)

    Returns:
        List of job dicts
    """
    try:
        response = dynamodb_client.query(
            TableName=TABLE_NAME,
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': {'S': f'WORKFLOW#{workflow_id}'},
                ':sk': {'S': 'JOB#'}
            },
            Limit=limit
        )

        jobs = [deserialize_item(item) for item in response.get('Items', [])]
        logger.info(f"Listed {len(jobs)} jobs for workflow {workflow_id}")
        return jobs

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        return []


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_or_create_application(account_id: str, application_name: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Get existing application or create new one.

    Args:
        account_id: Account ID
        application_name: Application name
        **kwargs: Additional fields for creation

    Returns:
        Application dict or None if failed
    """
    # Try to get existing
    app = get_application_by_name(account_id, application_name)
    if app:
        return app

    # Create new
    logger.info(f"Application not found, creating: {account_id}/{application_name}")
    return create_application(account_id, application_name, **kwargs)


def get_or_create_workflow(application_id: str, workflow_type: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Get existing active workflow or create new one.

    Args:
        application_id: Application ID
        workflow_type: Workflow type (e.g., 'code_analysis_v3')
        **kwargs: Additional fields for creation

    Returns:
        Workflow dict or None if failed
    """
    # For now, always create a new workflow for each job
    # In the future, we could check for existing pending/running workflows
    workflow_name = kwargs.get('name', workflow_type.replace('_', ' ').title())
    return create_workflow(application_id, workflow_name, workflow_type, **kwargs)


# ============================================================
# CONNECTION TEST
# ============================================================

def test_connection() -> bool:
    """
    Test DynamoDB connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        response = dynamodb_client.describe_table(TableName=TABLE_NAME)
        logger.info(f"DynamoDB connection successful - table: {TABLE_NAME}")
        return True
    except Exception as e:
        logger.error(f"DynamoDB connection failed: {e}")
        return False
