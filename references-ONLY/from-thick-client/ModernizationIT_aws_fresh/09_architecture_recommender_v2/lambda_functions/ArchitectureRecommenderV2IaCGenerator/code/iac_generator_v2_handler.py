"""
Architecture Recommender V2 - IaC Generator Handler
Lambda: ArchitectureRecommenderV2IaCGenerator

Purpose: Generate Infrastructure as Code (AWS CDK TypeScript)

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Generates AWS CDK TypeScript templates
"""

import json
import boto3
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    IaC Generator - Generate AWS CDK Infrastructure as Code

    Input:
    {
        "job_id": "ar2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "iac_templates": [...],
        "format": "AWS CDK (TypeScript)"
    }
    """
    try:
        print("=" * 80)
        print("ARCHITECTURE RECOMMENDER V2 - IAC GENERATOR")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        # Read architecture analysis and cost estimates
        base_path = f"{scout_account_id}/{application_name}"
        analysis_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/architecture_analysis.json"
        cost_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/cost_estimates.json"

        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=analysis_key)
        architecture_analysis = json.loads(response['Body'].read().decode('utf-8'))

        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=cost_key)
        cost_estimates = json.loads(response['Body'].read().decode('utf-8'))

        print(f"\nGenerating CDK templates...")

        # Generate CDK stacks
        vpc_stack = generate_vpc_stack(architecture_analysis, application_name)
        iam_stack = generate_iam_stack(architecture_analysis, application_name)
        compute_stack = generate_compute_stack(architecture_analysis, application_name)
        database_stack = generate_database_stack(architecture_analysis, application_name)

        # Write CDK templates to S3
        templates_written = []

        templates = [
            ('vpc-stack.ts', vpc_stack),
            ('iam-stack.ts', iam_stack),
            ('compute-stack.ts', compute_stack),
            ('database-stack.ts', database_stack)
        ]

        for template_name, template_code in templates:
            template_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/iac_templates/cdk/{template_name}"

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=template_key,
                Body=template_code,
                ContentType='text/plain'
            )

            templates_written.append(f"s3://{BUCKET_NAME}/{template_key}")
            print(f"✓ {template_name}")

        # Generate final architecture recommendations artifact
        final_recommendations = {
            'job_id': job_id,
            'generated_at': event.get('started_at', ''),
            'summary': architecture_analysis.get('summary', {}),
            'service_mappings': architecture_analysis.get('service_mappings', []),
            'database_strategy': architecture_analysis.get('database_strategy', {}),
            'api_design': architecture_analysis.get('api_design', {}),
            'compute_summary': architecture_analysis.get('compute_summary', {}),
            'storage_strategy': architecture_analysis.get('storage_strategy', {}),
            'security_architecture': architecture_analysis.get('security_recommendations', {}),
            'migration_phases': architecture_analysis.get('migration_phases', []),
            'infrastructure_as_code': {
                'format': 'AWS CDK (TypeScript)',
                'artifacts': [t.split('/')[-1] for t in templates_written],
                'deployment_instructions': 'Run "cdk deploy --all" to provision complete infrastructure'
            },
            'cost_breakdown': cost_estimates.get('cost_breakdown', {})
        }

        # Write final recommendations
        final_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/architecture_recommendations.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=final_key,
            Body=json.dumps(final_recommendations, indent=2),
            ContentType='application/json'
        )

        print(f"\n✓ Final recommendations: s3://{BUCKET_NAME}/{final_key}")

        # Update status to completed
        update_status(scout_account_id, application_name, job_id, {
            'state': 'completed',
            'status': 'completed',
            'phase': 'completed',
            'progress': 100,
            'message': 'Architecture recommendations completed successfully',
            'completed_at': event.get('started_at', '')
        })

        return {
            'iac_templates': templates_written,
            'format': 'AWS CDK (TypeScript)',
            'final_recommendations': f"s3://{BUCKET_NAME}/{final_key}"
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def generate_vpc_stack(architecture: Dict[str, Any], app_name: str) -> str:
    """Generate VPC stack CDK code"""

    security = architecture.get('security_recommendations', {})
    vpc_required = security.get('vpc_required', True)

    if not vpc_required:
        return "// VPC not required for this architecture\n"

    return f"""import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import {{ Construct }} from 'constructs';

export class VpcStack extends cdk.Stack {{
  public readonly vpc: ec2.Vpc;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {{
    super(scope, id, props);

    // VPC with public and private subnets
    this.vpc = new ec2.Vpc(this, '{app_name}Vpc', {{
      maxAzs: 2,
      natGateways: 2,
      subnetConfiguration: [
        {{
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        }},
        {{
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        }},
      ],
    }});

    // VPC Flow Logs for security monitoring
    new ec2.FlowLog(this, 'VpcFlowLog', {{
      resourceType: ec2.FlowLogResourceType.fromVpc(this.vpc),
    }});

    // Outputs
    new cdk.CfnOutput(this, 'VpcId', {{
      value: this.vpc.vpcId,
      description: 'VPC ID',
    }});
  }}
}}
"""


def generate_iam_stack(architecture: Dict[str, Any], app_name: str) -> str:
    """Generate IAM stack CDK code"""

    return f"""import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import {{ Construct }} from 'constructs';

export class IamStack extends cdk.Stack {{
  public readonly lambdaExecutionRole: iam.Role;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {{
    super(scope, id, props);

    // Lambda Execution Role
    this.lambdaExecutionRole = new iam.Role(this, 'LambdaExecutionRole', {{
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
    }});

    // Add RDS access permissions
    this.lambdaExecutionRole.addToPolicy(new iam.PolicyStatement({{
      actions: [
        'rds-data:ExecuteStatement',
        'rds-data:BatchExecuteStatement',
      ],
      resources: ['*'],
    }}));

    // Add S3 access permissions
    this.lambdaExecutionRole.addToPolicy(new iam.PolicyStatement({{
      actions: [
        's3:GetObject',
        's3:PutObject',
      ],
      resources: ['arn:aws:s3:::{app_name.lower()}-*/*'],
    }}));

    // Outputs
    new cdk.CfnOutput(this, 'LambdaExecutionRoleArn', {{
      value: this.lambdaExecutionRole.roleArn,
      description: 'Lambda Execution Role ARN',
    }});
  }}
}}
"""


def generate_compute_stack(architecture: Dict[str, Any], app_name: str) -> str:
    """Generate compute stack CDK code"""

    service_mappings = architecture.get('service_mappings', [])
    lambda_count = len([s for s in service_mappings if s.get('aws_service') == 'Lambda'])

    if lambda_count == 0:
        return "// No Lambda functions in this architecture\n"

    lambda_defs = []
    for i, mapping in enumerate(service_mappings[:3]):  # Show first 3 as examples
        if mapping.get('aws_service') == 'Lambda':
            func_name = mapping.get('function_name', f'Function{i+1}')
            memory = mapping.get('memory_mb', 512)
            timeout = mapping.get('timeout_seconds', 300)

            lambda_defs.append(f"""
    // Lambda Function: {func_name}
    const {func_name.lower()} = new lambda.Function(this, '{func_name}', {{
      runtime: lambda.Runtime.JAVA_17,
      handler: 'com.example.{func_name}::handleRequest',
      code: lambda.Code.fromAsset('lambda/{func_name.lower()}'),
      memorySize: {memory},
      timeout: cdk.Duration.seconds({timeout}),
      role: props.lambdaExecutionRole,
      vpc: props.vpc,
    }});""")

    return f"""import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import {{ Construct }} from 'constructs';

interface ComputeStackProps extends cdk.StackProps {{
  readonly vpc: cdk.aws_ec2.IVpc;
  readonly lambdaExecutionRole: cdk.aws_iam.IRole;
}}

export class ComputeStack extends cdk.Stack {{
  constructor(scope: Construct, id: string, props: ComputeStackProps) {{
    super(scope, id, props);
{''.join(lambda_defs)}

    // CloudWatch Events Rule (example - daily at 2 AM)
    const rule = new events.Rule(this, 'DailyTrigger', {{
      schedule: events.Schedule.cron({{ hour: '2', minute: '0' }}),
    }});

    // NOTE: Add more Lambda functions and triggers as needed
  }}
}}
"""


def generate_database_stack(architecture: Dict[str, Any], app_name: str) -> str:
    """Generate database stack CDK code"""

    database_strategy = architecture.get('database_strategy', {})
    primary_db = database_strategy.get('primary_database', 'None')

    if not primary_db or primary_db == 'None':
        return "// No database required for this architecture\n"

    if 'RDS' in primary_db or 'PostgreSQL' in primary_db:
        instance_class = database_strategy.get('instance_class', 'db.t4g.medium')
        storage_gb = database_strategy.get('storage_gb', 100)
        multi_az = database_strategy.get('multi_az', False)

        return f"""import * as cdk from 'aws-cdk-lib';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import {{ Construct }} from 'constructs';

interface DatabaseStackProps extends cdk.StackProps {{
  readonly vpc: cdk.aws_ec2.IVpc;
}}

export class DatabaseStack extends cdk.Stack {{
  public readonly database: rds.DatabaseInstance;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {{
    super(scope, id, props);

    // RDS PostgreSQL Instance
    this.database = new rds.DatabaseInstance(this, '{app_name}Database', {{
      engine: rds.DatabaseInstanceEngine.postgres({{
        version: rds.PostgresEngineVersion.VER_15,
      }}),
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T4G,
        ec2.InstanceSize.MEDIUM
      ),
      vpc: props.vpc,
      vpcSubnets: {{
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      }},
      multiAz: {str(multi_az).lower()},
      allocatedStorage: {storage_gb},
      maxAllocatedStorage: {storage_gb * 2},
      databaseName: '{app_name.lower()}db',
      backupRetention: cdk.Duration.days(7),
      deleteAutomatedBackups: false,
      removalPolicy: cdk.RemovalPolicy.SNAPSHOT,
    }});

    // Outputs
    new cdk.CfnOutput(this, 'DatabaseEndpoint', {{
      value: this.database.dbInstanceEndpointAddress,
      description: 'Database Endpoint',
    }});
  }}
}}
"""

    return "// Database type not yet supported in CDK generator\n"


def update_status(account_id: str, app_name: str, job_id: str, updates: Dict[str, Any]):
    """Update job status in S3"""
    try:
        status_key = f"{account_id}/{app_name}/architecture_v2/jobs/{job_id}/status.json"

        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
        status = json.loads(response['Body'].read().decode('utf-8'))

        status.update(updates)

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status, indent=2),
            ContentType='application/json'
        )

        print(f"Updated status: {updates}")

    except Exception as e:
        print(f"Error updating status: {str(e)}")
