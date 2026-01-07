"""
Java Generation V2 - AWS Integration Generator Handler
Lambda: JavaGenV2AWSIntegrationGenerator

Purpose: Generate AWS integration code based on Architecture Recommender V2 output

V2 Design Principles:
- NO HARDCODING
- Template-driven (inline templates)
- Generates based on AWS recommendations
- Creates DynamoDB repos, SQS handlers, S3 clients, etc.
"""

import json
import boto3
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from jinja2 import Template

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v2')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate AWS integration code from recommendations

    Input:
    {
        "job_id": "jgv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "integrations_generated": 8,
        "files_created": [list of integration files]
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - AWS INTEGRATION GENERATOR")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v2/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'generating_aws_integrations', 85, 'Generating AWS integration code...')

        # Read generation plan
        plan_key = f"{job_base}/generation_plan.json"
        generation_plan = read_json(plan_key)

        # Read project metadata
        project_metadata = read_json(f"{job_base}/project_metadata.json")
        projects = project_metadata.get('projects', [])

        # Read AWS recommendations
        input_ref = read_json(f"{job_base}/input_ref.json")
        aws_recommendations_key = input_ref['artifacts'].get('aws_recommendations', '')
        aws_recommendations = read_json(aws_recommendations_key)

        if not aws_recommendations:
            print("WARNING: No AWS recommendations found - skipping AWS integration generation")
            return {
                'statusCode': 200,
                'integrations_generated': 0,
                'files_created': []
            }

        print(f"Processing AWS recommendations...")

        files_created = []

        # Generate AWS integrations for each project
        for project in projects:
            service_name = project['service_name']
            base_package = project['base_package']
            project_base = project['base_path']

            print(f"\n=== Generating AWS integrations for {service_name} ===")

            # Parse recommendations
            recommendations = aws_recommendations.get('recommendations', {})

            # Generate DynamoDB integration if recommended
            if has_dynamodb_recommendation(recommendations):
                print("  Generating DynamoDB repository...")
                dynamodb_code = generate_dynamodb_repository(base_package, service_name)
                dynamodb_file = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/aws/DynamoDBRepository.java"
                write_file(dynamodb_file, dynamodb_code)
                files_created.append(dynamodb_file)

            # Generate SQS handler if recommended
            if has_sqs_recommendation(recommendations):
                print("  Generating SQS message handler...")
                sqs_code = generate_sqs_handler(base_package, service_name)
                sqs_file = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/aws/SQSMessageHandler.java"
                write_file(sqs_file, sqs_code)
                files_created.append(sqs_file)

            # Generate S3 client if recommended
            if has_s3_recommendation(recommendations):
                print("  Generating S3 client...")
                s3_code = generate_s3_client(base_package, service_name)
                s3_file = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/aws/S3FileService.java"
                write_file(s3_file, s3_code)
                files_created.append(s3_file)

            # Generate EventBridge publisher if recommended
            if has_eventbridge_recommendation(recommendations):
                print("  Generating EventBridge publisher...")
                eb_code = generate_eventbridge_publisher(base_package, service_name)
                eb_file = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/aws/EventBridgePublisher.java"
                write_file(eb_file, eb_code)
                files_created.append(eb_file)

            # Generate AWS Configuration
            print("  Generating AWS configuration...")
            config_code = generate_aws_config(base_package, recommendations)
            config_file = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/config/AWSConfig.java"
            write_file(config_file, config_code)
            files_created.append(config_file)

        print(f"\n✓ Total AWS integration files generated: {len(files_created)}")

        # Update status
        update_status(job_base, 'running', 'aws_integrations_complete', 90, f'Generated {len(files_created)} AWS integration files')

        return {
            'statusCode': 200,
            'integrations_generated': len(files_created),
            'files_created': files_created
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def has_dynamodb_recommendation(recommendations: Dict[str, Any]) -> bool:
    """Check if DynamoDB is recommended"""
    database = recommendations.get('database', {})
    return 'dynamodb' in database.get('primary', '').lower()


def has_sqs_recommendation(recommendations: Dict[str, Any]) -> bool:
    """Check if SQS is recommended"""
    messaging = recommendations.get('messaging', {})
    return 'sqs' in str(messaging).lower()


def has_s3_recommendation(recommendations: Dict[str, Any]) -> bool:
    """Check if S3 is recommended"""
    storage = recommendations.get('storage', {})
    return 's3' in str(storage).lower()


def has_eventbridge_recommendation(recommendations: Dict[str, Any]) -> bool:
    """Check if EventBridge is recommended"""
    events = recommendations.get('events', {})
    return 'eventbridge' in str(events).lower()


def generate_dynamodb_repository(package_name: str, service_name: str) -> str:
    """Generate DynamoDB repository class"""
    template_str = """package {{ package_name }}.aws;

import org.springframework.stereotype.Repository;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbEnhancedClient;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbTable;
import software.amazon.awssdk.enhanced.dynamodb.TableSchema;
import software.amazon.awssdk.enhanced.dynamodb.Key;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.util.Optional;

/**
 * DynamoDB Repository
 * Provides DynamoDB access for {{ service_name }}
 * Generated from AWS Architecture recommendations
 */
@Repository
@RequiredArgsConstructor
@Slf4j
public class DynamoDBRepository<T> {

    private final DynamoDbEnhancedClient dynamoDbEnhancedClient;

    /**
     * Get DynamoDB table
     */
    public DynamoDbTable<T> getTable(String tableName, Class<T> itemClass) {
        return dynamoDbEnhancedClient.table(tableName, TableSchema.fromBean(itemClass));
    }

    /**
     * Save item to DynamoDB
     */
    public void save(String tableName, T item, Class<T> itemClass) {
        log.info("Saving item to DynamoDB table: {}", tableName);
        DynamoDbTable<T> table = getTable(tableName, itemClass);
        table.putItem(item);
    }

    /**
     * Get item from DynamoDB by key
     */
    public Optional<T> getById(String tableName, String id, Class<T> itemClass) {
        log.info("Getting item from DynamoDB table: {} with id: {}", tableName, id);
        DynamoDbTable<T> table = getTable(tableName, itemClass);
        Key key = Key.builder().partitionValue(id).build();
        T item = table.getItem(key);
        return Optional.ofNullable(item);
    }

    /**
     * Delete item from DynamoDB
     */
    public void delete(String tableName, String id, Class<T> itemClass) {
        log.info("Deleting item from DynamoDB table: {} with id: {}", tableName, id);
        DynamoDbTable<T> table = getTable(tableName, itemClass);
        Key key = Key.builder().partitionValue(id).build();
        table.deleteItem(key);
    }
}
"""
    template = Template(template_str)
    return template.render(package_name=package_name, service_name=service_name)


def generate_sqs_handler(package_name: str, service_name: str) -> str:
    """Generate SQS message handler"""
    template_str = """package {{ package_name }}.aws;

import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.util.List;

/**
 * SQS Message Handler
 * Handles SQS message operations for {{ service_name }}
 * Generated from AWS Architecture recommendations
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class SQSMessageHandler {

    private final SqsClient sqsClient;

    /**
     * Send message to SQS queue
     */
    public void sendMessage(String queueUrl, String messageBody) {
        log.info("Sending message to SQS queue: {}", queueUrl);

        SendMessageRequest request = SendMessageRequest.builder()
                .queueUrl(queueUrl)
                .messageBody(messageBody)
                .build();

        SendMessageResponse response = sqsClient.sendMessage(request);
        log.info("Message sent with ID: {}", response.messageId());
    }

    /**
     * Receive messages from SQS queue
     */
    public List<Message> receiveMessages(String queueUrl, int maxMessages) {
        log.info("Receiving messages from SQS queue: {}", queueUrl);

        ReceiveMessageRequest request = ReceiveMessageRequest.builder()
                .queueUrl(queueUrl)
                .maxNumberOfMessages(maxMessages)
                .waitTimeSeconds(10)
                .build();

        ReceiveMessageResponse response = sqsClient.receiveMessage(request);
        return response.messages();
    }

    /**
     * Delete message from SQS queue
     */
    public void deleteMessage(String queueUrl, String receiptHandle) {
        log.info("Deleting message from SQS queue: {}", queueUrl);

        DeleteMessageRequest request = DeleteMessageRequest.builder()
                .queueUrl(queueUrl)
                .receiptHandle(receiptHandle)
                .build();

        sqsClient.deleteMessage(request);
    }
}
"""
    template = Template(template_str)
    return template.render(package_name=package_name, service_name=service_name)


def generate_s3_client(package_name: str, service_name: str) -> str:
    """Generate S3 file service"""
    template_str = """package {{ package_name }}.aws;

import org.springframework.stereotype.Service;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.core.sync.ResponseTransformer;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.io.InputStream;

/**
 * S3 File Service
 * Handles S3 file operations for {{ service_name }}
 * Generated from AWS Architecture recommendations
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class S3FileService {

    private final S3Client s3Client;

    /**
     * Upload file to S3
     */
    public void uploadFile(String bucketName, String key, byte[] content) {
        log.info("Uploading file to S3: bucket={}, key={}", bucketName, key);

        PutObjectRequest request = PutObjectRequest.builder()
                .bucket(bucketName)
                .key(key)
                .build();

        s3Client.putObject(request, RequestBody.fromBytes(content));
        log.info("File uploaded successfully");
    }

    /**
     * Download file from S3
     */
    public InputStream downloadFile(String bucketName, String key) {
        log.info("Downloading file from S3: bucket={}, key={}", bucketName, key);

        GetObjectRequest request = GetObjectRequest.builder()
                .bucket(bucketName)
                .key(key)
                .build();

        return s3Client.getObject(request, ResponseTransformer.toInputStream());
    }

    /**
     * Delete file from S3
     */
    public void deleteFile(String bucketName, String key) {
        log.info("Deleting file from S3: bucket={}, key={}", bucketName, key);

        DeleteObjectRequest request = DeleteObjectRequest.builder()
                .bucket(bucketName)
                .key(key)
                .build();

        s3Client.deleteObject(request);
    }

    /**
     * Check if file exists in S3
     */
    public boolean fileExists(String bucketName, String key) {
        log.info("Checking if file exists in S3: bucket={}, key={}", bucketName, key);

        try {
            HeadObjectRequest request = HeadObjectRequest.builder()
                    .bucket(bucketName)
                    .key(key)
                    .build();

            s3Client.headObject(request);
            return true;
        } catch (NoSuchKeyException e) {
            return false;
        }
    }
}
"""
    template = Template(template_str)
    return template.render(package_name=package_name, service_name=service_name)


def generate_eventbridge_publisher(package_name: str, service_name: str) -> str:
    """Generate EventBridge event publisher"""
    template_str = """package {{ package_name }}.aws;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.eventbridge.EventBridgeClient;
import software.amazon.awssdk.services.eventbridge.model.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * EventBridge Publisher
 * Publishes events to EventBridge for {{ service_name }}
 * Generated from AWS Architecture recommendations
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class EventBridgePublisher {

    private final EventBridgeClient eventBridgeClient;
    private final ObjectMapper objectMapper;

    /**
     * Publish event to EventBridge
     */
    public void publishEvent(String eventBusName, String source, String detailType, Object detail) {
        log.info("Publishing event to EventBridge: bus={}, source={}, type={}", eventBusName, source, detailType);

        try {
            String detailJson = objectMapper.writeValueAsString(detail);

            PutEventsRequestEntry entry = PutEventsRequestEntry.builder()
                    .eventBusName(eventBusName)
                    .source(source)
                    .detailType(detailType)
                    .detail(detailJson)
                    .build();

            PutEventsRequest request = PutEventsRequest.builder()
                    .entries(entry)
                    .build();

            PutEventsResponse response = eventBridgeClient.putEvents(request);

            if (response.failedEntryCount() > 0) {
                log.error("Failed to publish event: {}", response.entries());
            } else {
                log.info("Event published successfully");
            }

        } catch (JsonProcessingException e) {
            log.error("Error serializing event detail", e);
            throw new RuntimeException("Failed to publish event", e);
        }
    }
}
"""
    template = Template(template_str)
    return template.render(package_name=package_name, service_name=service_name)


def generate_aws_config(package_name: str, recommendations: Dict[str, Any]) -> str:
    """Generate AWS SDK configuration"""
    template_str = """package {{ package_name }}.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.regions.Region;
{% if has_dynamodb %}
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbEnhancedClient;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
{% endif %}
{% if has_sqs %}
import software.amazon.awssdk.services.sqs.SqsClient;
{% endif %}
{% if has_s3 %}
import software.amazon.awssdk.services.s3.S3Client;
{% endif %}
{% if has_eventbridge %}
import software.amazon.awssdk.services.eventbridge.EventBridgeClient;
{% endif %}

/**
 * AWS SDK Configuration
 * Configures AWS service clients
 * Generated from AWS Architecture recommendations
 */
@Configuration
public class AWSConfig {

    private static final Region AWS_REGION = Region.US_EAST_1;

    {% if has_dynamodb %}
    @Bean
    public DynamoDbClient dynamoDbClient() {
        return DynamoDbClient.builder()
                .region(AWS_REGION)
                .build();
    }

    @Bean
    public DynamoDbEnhancedClient dynamoDbEnhancedClient(DynamoDbClient dynamoDbClient) {
        return DynamoDbEnhancedClient.builder()
                .dynamoDbClient(dynamoDbClient)
                .build();
    }
    {% endif %}

    {% if has_sqs %}
    @Bean
    public SqsClient sqsClient() {
        return SqsClient.builder()
                .region(AWS_REGION)
                .build();
    }
    {% endif %}

    {% if has_s3 %}
    @Bean
    public S3Client s3Client() {
        return S3Client.builder()
                .region(AWS_REGION)
                .build();
    }
    {% endif %}

    {% if has_eventbridge %}
    @Bean
    public EventBridgeClient eventBridgeClient() {
        return EventBridgeClient.builder()
                .region(AWS_REGION)
                .build();
    }

    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper();
    }
    {% endif %}
}
"""
    template = Template(template_str)
    return template.render(
        package_name=package_name,
        has_dynamodb=has_dynamodb_recommendation(recommendations),
        has_sqs=has_sqs_recommendation(recommendations),
        has_s3=has_s3_recommendation(recommendations),
        has_eventbridge=has_eventbridge_recommendation(recommendations)
    )


def write_file(s3_key: str, content: str):
    """Write file to S3"""
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=content,
        ContentType='text/plain'
    )


def read_json(s3_key: str) -> Dict[str, Any]:
    """Read JSON from S3"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"WARNING: Could not read {s3_key}: {str(e)}")
        return {}


def update_status(job_base: str, state: str, phase: str, progress: int, message: str):
    """Update job status"""
    try:
        status_key = f"{job_base}/status.json"
        status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
        status_data = json.loads(status_response['Body'].read())

        status_data['state'] = state
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status: {state} / {phase} ({progress}%) - {message}")
    except Exception as e:
        print(f"ERROR updating status: {str(e)}")
