"""
IaC Generator for Architecture Recommender

Generates AWS CDK templates based on recommendations.
These are blueprints/starting points, not production-ready code.

Templates match the actual Java structure detected.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from api.models.architecture import (
    IaCOutput,
    IaCTemplate,
    ComputeRecommendation,
    DatabaseRecommendation,
    APIRecommendation,
    StorageRecommendation,
    SecurityRecommendation,
    ComputeService,
    DatabaseService,
)
from engines.architecture.analyzers.source_consolidator import ConsolidatedSources


class IaCGenerator:
    """Generates CDK templates based on recommendations."""

    def __init__(
        self,
        output_dir: str,
        application_name: str,
        sources: ConsolidatedSources,
        compute: ComputeRecommendation,
        database: DatabaseRecommendation,
        api: APIRecommendation,
        storage: Optional[StorageRecommendation] = None,
        security: Optional[SecurityRecommendation] = None
    ):
        """
        Initialize generator.

        Args:
            output_dir: Directory to write templates
            application_name: Application name for resource naming
            sources: Consolidated sources
            compute: Compute recommendation
            database: Database recommendation
            api: API recommendation
            storage: Optional storage recommendation
            security: Optional security recommendation
        """
        self.output_dir = Path(output_dir) / "iac_templates"
        self.app_name = self._sanitize_name(application_name)
        self.sources = sources
        self.compute = compute
        self.database = database
        self.api = api
        self.storage = storage
        self.security = security
        self.templates: List[IaCTemplate] = []

    def generate(self) -> IaCOutput:
        """
        Generate all IaC templates.

        Returns:
            IaCOutput with generated templates
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate templates based on recommendations
        self._generate_vpc_stack()
        self._generate_compute_stack()

        if self.database.service != DatabaseService.NONE:
            self._generate_database_stack()

        if self.api.required:
            self._generate_api_stack()

        if self.storage and self.storage.buckets:
            self._generate_storage_stack()

        # Generate main app file
        self._generate_app_file()

        # Determine deployment order
        deployment_order = ["vpc-stack"]
        if self.database.service != DatabaseService.NONE:
            deployment_order.append("database-stack")
        if self.storage and self.storage.buckets:
            deployment_order.append("storage-stack")
        deployment_order.append("compute-stack")
        if self.api.required:
            deployment_order.append("api-stack")

        return IaCOutput(
            templates=self.templates,
            deployment_order=deployment_order,
            total_resources=sum(len(t.resources) for t in self.templates)
        )

    def _sanitize_name(self, name: str) -> str:
        """Convert name to valid resource name."""
        import re
        # Remove special chars, convert to kebab-case
        name = re.sub(r'[^a-zA-Z0-9]', '-', name.lower())
        name = re.sub(r'-+', '-', name)
        return name.strip('-')

    def _generate_vpc_stack(self) -> None:
        """Generate VPC stack."""
        content = f'''import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import {{ Construct }} from 'constructs';

/**
 * VPC Stack for {self.app_name}
 * Generated: {datetime.now().isoformat()}
 *
 * Creates:
 * - VPC with public and private subnets
 * - NAT Gateway for private subnet internet access
 * - VPC Endpoints for AWS services
 */
export class VpcStack extends cdk.Stack {{
  public readonly vpc: ec2.Vpc;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {{
    super(scope, id, props);

    // Create VPC
    this.vpc = new ec2.Vpc(this, '{self.app_name}-vpc', {{
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        {{
          cidrMask: 24,
          name: 'public',
          subnetType: ec2.SubnetType.PUBLIC,
        }},
        {{
          cidrMask: 24,
          name: 'private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        }},
      ],
    }});

    // Add VPC Endpoints for AWS services
    this.vpc.addGatewayEndpoint('S3Endpoint', {{
      service: ec2.GatewayVpcEndpointAwsService.S3,
    }});

    this.vpc.addGatewayEndpoint('DynamoDBEndpoint', {{
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
    }});

    // Output VPC ID
    new cdk.CfnOutput(this, 'VpcId', {{
      value: this.vpc.vpcId,
      description: 'VPC ID for {self.app_name}',
      exportName: '{self.app_name}-vpc-id',
    }});
  }}
}}
'''
        file_path = self.output_dir / "vpc-stack.ts"
        file_path.write_text(content)

        self.templates.append(IaCTemplate(
            template_name="vpc-stack",
            template_type="cdk",
            file_path=str(file_path),
            resources=["VPC", "NAT Gateway", "VPC Endpoints"],
            dependencies=[]
        ))

    def _generate_compute_stack(self) -> None:
        """Generate compute stack based on recommendation."""
        if self.compute.service == ComputeService.LAMBDA:
            self._generate_lambda_stack()
        else:
            self._generate_fargate_stack()

    def _generate_lambda_stack(self) -> None:
        """Generate Lambda functions stack."""
        # Build function definitions from recommendation
        function_defs = []
        for func in self.compute.functions:
            function_defs.append(f'''
    // {func.name} - Source: {func.source_class}
    const {self._to_var_name(func.name)} = new lambda.Function(this, '{func.name}', {{
      runtime: lambda.Runtime.JAVA_17,
      handler: 'com.{self.app_name}.{func.source_class}::handleRequest',
      code: lambda.Code.fromAsset('lambda/{func.name}'),
      memorySize: {func.memory_mb},
      timeout: cdk.Duration.seconds({func.timeout_seconds}),
      vpc: props.vpc,
      environment: {{
        JAVA_TOOL_OPTIONS: '-XX:+TieredCompilation -XX:TieredStopAtLevel=1',
      }},
    }});''')

        content = f'''import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import {{ Construct }} from 'constructs';

interface ComputeStackProps extends cdk.StackProps {{
  vpc: ec2.IVpc;
}}

/**
 * Lambda Compute Stack for {self.app_name}
 * Generated: {datetime.now().isoformat()}
 *
 * Creates {len(self.compute.functions)} Lambda functions:
{chr(10).join(f" * - {f.name} ({f.trigger})" for f in self.compute.functions)}
 */
export class ComputeStack extends cdk.Stack {{
  constructor(scope: Construct, id: string, props: ComputeStackProps) {{
    super(scope, id, props);
{"".join(function_defs) if function_defs else '''
    // No Lambda functions detected - add your functions here
    // const myFunction = new lambda.Function(this, 'MyFunction', {
    //   runtime: lambda.Runtime.JAVA_17,
    //   handler: 'com.example.Handler::handleRequest',
    //   code: lambda.Code.fromAsset('lambda/my-function'),
    // });
'''}
  }}
}}
'''
        file_path = self.output_dir / "compute-stack.ts"
        file_path.write_text(content)

        self.templates.append(IaCTemplate(
            template_name="compute-stack",
            template_type="cdk",
            file_path=str(file_path),
            resources=[f.name for f in self.compute.functions],
            dependencies=["vpc-stack"]
        ))

    def _generate_fargate_stack(self) -> None:
        """Generate ECS/Fargate stack."""
        content = f'''import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import {{ Construct }} from 'constructs';

interface ComputeStackProps extends cdk.StackProps {{
  vpc: ec2.IVpc;
}}

/**
 * ECS/Fargate Compute Stack for {self.app_name}
 * Generated: {datetime.now().isoformat()}
 */
export class ComputeStack extends cdk.Stack {{
  constructor(scope: Construct, id: string, props: ComputeStackProps) {{
    super(scope, id, props);

    // Create ECS Cluster
    const cluster = new ecs.Cluster(this, '{self.app_name}-cluster', {{
      vpc: props.vpc,
      containerInsights: true,
    }});

    // Create Fargate Service
    const service = new ecsPatterns.ApplicationLoadBalancedFargateService(
      this,
      '{self.app_name}-service',
      {{
        cluster,
        cpu: 1024,
        memoryLimitMiB: 2048,
        desiredCount: 2,
        taskImageOptions: {{
          image: ecs.ContainerImage.fromRegistry(
            'ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/{self.app_name}:latest'
          ),
          containerPort: 8080,
        }},
        publicLoadBalancer: true,
      }}
    );

    // Auto-scaling
    const scaling = service.service.autoScaleTaskCount({{
      minCapacity: 2,
      maxCapacity: 10,
    }});

    scaling.scaleOnCpuUtilization('CpuScaling', {{
      targetUtilizationPercent: 70,
    }});
  }}
}}
'''
        file_path = self.output_dir / "compute-stack.ts"
        file_path.write_text(content)

        self.templates.append(IaCTemplate(
            template_name="compute-stack",
            template_type="cdk",
            file_path=str(file_path),
            resources=["ECS Cluster", "Fargate Service", "ALB"],
            dependencies=["vpc-stack"]
        ))

    def _generate_database_stack(self) -> None:
        """Generate database stack."""
        if self.database.service in [DatabaseService.AURORA_POSTGRESQL, DatabaseService.AURORA_MYSQL]:
            self._generate_aurora_stack()
        elif self.database.service == DatabaseService.DYNAMODB:
            self._generate_dynamodb_stack()

    def _generate_aurora_stack(self) -> None:
        """Generate Aurora stack."""
        engine = "AURORA_POSTGRESQL" if self.database.service == DatabaseService.AURORA_POSTGRESQL else "AURORA_MYSQL"
        engine_import = "AuroraPostgresEngineVersion.VER_15_4" if "POSTGRESQL" in engine else "AuroraMysqlEngineVersion.VER_3_04_0"

        content = f'''import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import {{ Construct }} from 'constructs';

interface DatabaseStackProps extends cdk.StackProps {{
  vpc: ec2.IVpc;
}}

/**
 * Aurora Database Stack for {self.app_name}
 * Generated: {datetime.now().isoformat()}
 *
 * Engine: {self.database.service.value}
 * Instance: {self.database.instance_class}
 * Storage: {self.database.storage_gb} GB
 * Multi-AZ: {self.database.multi_az}
 */
export class DatabaseStack extends cdk.Stack {{
  public readonly cluster: rds.DatabaseCluster;
  public readonly secret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {{
    super(scope, id, props);

    // Create database credentials secret
    this.secret = new secretsmanager.Secret(this, '{self.app_name}-db-secret', {{
      secretName: '{self.app_name}/database',
      generateSecretString: {{
        secretStringTemplate: JSON.stringify({{ username: 'admin' }}),
        generateStringKey: 'password',
        excludePunctuation: true,
      }},
    }});

    // Create Aurora cluster
    this.cluster = new rds.DatabaseCluster(this, '{self.app_name}-db', {{
      engine: rds.DatabaseClusterEngine.{'auroraPostgres' if 'POSTGRESQL' in engine else 'auroraMysql'}({{
        version: rds.{engine_import},
      }}),
      credentials: rds.Credentials.fromSecret(this.secret),
      instanceProps: {{
        vpc: props.vpc,
        vpcSubnets: {{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }},
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.T4G,
          ec2.InstanceSize.MEDIUM
        ),
      }},
      instances: {2 if self.database.multi_az else 1},
      storageEncrypted: true,
      deletionProtection: true,
      backup: {{
        retention: cdk.Duration.days(7),
      }},
    }});

    // Output endpoints
    new cdk.CfnOutput(this, 'ClusterEndpoint', {{
      value: this.cluster.clusterEndpoint.hostname,
      exportName: '{self.app_name}-db-endpoint',
    }});
  }}
}}
'''
        file_path = self.output_dir / "database-stack.ts"
        file_path.write_text(content)

        self.templates.append(IaCTemplate(
            template_name="database-stack",
            template_type="cdk",
            file_path=str(file_path),
            resources=["Aurora Cluster", "Secrets Manager Secret"],
            dependencies=["vpc-stack"]
        ))

    def _generate_dynamodb_stack(self) -> None:
        """Generate DynamoDB stack."""
        content = f'''import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import {{ Construct }} from 'constructs';

/**
 * DynamoDB Stack for {self.app_name}
 * Generated: {datetime.now().isoformat()}
 */
export class DatabaseStack extends cdk.Stack {{
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {{
    super(scope, id, props);

    // Create DynamoDB table
    const table = new dynamodb.Table(this, '{self.app_name}-table', {{
      tableName: '{self.app_name}',
      partitionKey: {{
        name: 'pk',
        type: dynamodb.AttributeType.STRING,
      }},
      sortKey: {{
        name: 'sk',
        type: dynamodb.AttributeType.STRING,
      }},
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
    }});

    // Add GSI for common access patterns
    table.addGlobalSecondaryIndex({{
      indexName: 'gsi1',
      partitionKey: {{
        name: 'gsi1pk',
        type: dynamodb.AttributeType.STRING,
      }},
      sortKey: {{
        name: 'gsi1sk',
        type: dynamodb.AttributeType.STRING,
      }},
    }});
  }}
}}
'''
        file_path = self.output_dir / "database-stack.ts"
        file_path.write_text(content)

        self.templates.append(IaCTemplate(
            template_name="database-stack",
            template_type="cdk",
            file_path=str(file_path),
            resources=["DynamoDB Table", "GSI"],
            dependencies=[]
        ))

    def _generate_api_stack(self) -> None:
        """Generate API Gateway stack."""
        api_type = self.api.api_type or "REST"

        content = f'''import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import {{ Construct }} from 'constructs';

interface ApiStackProps extends cdk.StackProps {{
  lambdaFunctions: Record<string, lambda.IFunction>;
}}

/**
 * API Gateway Stack for {self.app_name}
 * Generated: {datetime.now().isoformat()}
 *
 * Type: {api_type}
 * Auth: {self.api.auth_type}
 */
export class ApiStack extends cdk.Stack {{
  constructor(scope: Construct, id: string, props: ApiStackProps) {{
    super(scope, id, props);

    // Create API Gateway
    const api = new apigateway.RestApi(this, '{self.app_name}-api', {{
      restApiName: '{self.app_name}',
      description: 'API for {self.app_name}',
      deployOptions: {{
        stageName: 'prod',
        tracingEnabled: true,
      }},
      defaultCorsPreflightOptions: {{
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      }},
    }});

    // Add resources and methods based on Lambda functions
    // Each controller maps to an API resource
    Object.entries(props.lambdaFunctions).forEach(([name, fn]) => {{
      const resource = api.root.addResource(name.replace('-service', ''));
      resource.addMethod('GET', new apigateway.LambdaIntegration(fn));
      resource.addMethod('POST', new apigateway.LambdaIntegration(fn));
      resource.addMethod('PUT', new apigateway.LambdaIntegration(fn));
      resource.addMethod('DELETE', new apigateway.LambdaIntegration(fn));
    }});

    // Output API URL
    new cdk.CfnOutput(this, 'ApiUrl', {{
      value: api.url,
      exportName: '{self.app_name}-api-url',
    }});
  }}
}}
'''
        file_path = self.output_dir / "api-stack.ts"
        file_path.write_text(content)

        self.templates.append(IaCTemplate(
            template_name="api-stack",
            template_type="cdk",
            file_path=str(file_path),
            resources=["API Gateway", "API Resources", "Lambda Integrations"],
            dependencies=["compute-stack"]
        ))

    def _generate_storage_stack(self) -> None:
        """Generate S3 storage stack."""
        bucket_defs = []
        for bucket in self.storage.buckets:
            storage_class = "INTELLIGENT_TIERING" if bucket.storage_class == "STANDARD" else bucket.storage_class.upper()
            bucket_defs.append(f'''
    new s3.Bucket(this, '{bucket.name_suffix}', {{
      bucketName: `${{this.account}}-{self.app_name}-{bucket.name_suffix}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    }});''')

        content = f'''import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import {{ Construct }} from 'constructs';

/**
 * S3 Storage Stack for {self.app_name}
 * Generated: {datetime.now().isoformat()}
 */
export class StorageStack extends cdk.Stack {{
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {{
    super(scope, id, props);
{"".join(bucket_defs)}
  }}
}}
'''
        file_path = self.output_dir / "storage-stack.ts"
        file_path.write_text(content)

        self.templates.append(IaCTemplate(
            template_name="storage-stack",
            template_type="cdk",
            file_path=str(file_path),
            resources=[b.name_suffix for b in self.storage.buckets],
            dependencies=[]
        ))

    def _generate_app_file(self) -> None:
        """Generate main CDK app file."""
        content = f'''#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import {{ VpcStack }} from './vpc-stack';
import {{ ComputeStack }} from './compute-stack';
{'import { DatabaseStack } from "./database-stack";' if self.database.service != DatabaseService.NONE else ''}
{'import { ApiStack } from "./api-stack";' if self.api.required else ''}
{'import { StorageStack } from "./storage-stack";' if self.storage and self.storage.buckets else ''}

/**
 * {self.app_name} Infrastructure
 * Generated: {datetime.now().isoformat()}
 *
 * Deployment order:
 * 1. VPC Stack
 * 2. Database Stack (if needed)
 * 3. Storage Stack (if needed)
 * 4. Compute Stack
 * 5. API Stack (if needed)
 */
const app = new cdk.App();

const env = {{
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
}};

// 1. VPC
const vpcStack = new VpcStack(app, '{self.app_name}-vpc', {{ env }});

{'// 2. Database' if self.database.service != DatabaseService.NONE else ''}
{'const dbStack = new DatabaseStack(app, "' + self.app_name + '-database", {' if self.database.service != DatabaseService.NONE else ''}
{'  env,' if self.database.service != DatabaseService.NONE else ''}
{'  vpc: vpcStack.vpc,' if self.database.service != DatabaseService.NONE else ''}
{'});' if self.database.service != DatabaseService.NONE else ''}

{'// 3. Storage' if self.storage and self.storage.buckets else ''}
{'const storageStack = new StorageStack(app, "' + self.app_name + '-storage", { env });' if self.storage and self.storage.buckets else ''}

// 4. Compute
const computeStack = new ComputeStack(app, '{self.app_name}-compute', {{
  env,
  vpc: vpcStack.vpc,
}});

{'// 5. API' if self.api.required else ''}
{'const apiStack = new ApiStack(app, "' + self.app_name + '-api", {' if self.api.required else ''}
{'  env,' if self.api.required else ''}
{'  lambdaFunctions: computeStack.functions,' if self.api.required else ''}
{'});' if self.api.required else ''}

app.synth();
'''
        file_path = self.output_dir / "app.ts"
        file_path.write_text(content)

        self.templates.append(IaCTemplate(
            template_name="app",
            template_type="cdk",
            file_path=str(file_path),
            resources=[],
            dependencies=[]
        ))

    def _to_var_name(self, name: str) -> str:
        """Convert kebab-case to camelCase."""
        parts = name.split('-')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def generate_iac(
    output_dir: str,
    application_name: str,
    sources: ConsolidatedSources,
    compute: ComputeRecommendation,
    database: DatabaseRecommendation,
    api: APIRecommendation,
    storage: Optional[StorageRecommendation] = None,
    security: Optional[SecurityRecommendation] = None
) -> IaCOutput:
    """
    Convenience function to generate IaC.

    Args:
        output_dir: Output directory
        application_name: Application name
        sources: Consolidated sources
        compute: Compute recommendation
        database: Database recommendation
        api: API recommendation
        storage: Optional storage recommendation
        security: Optional security recommendation

    Returns:
        IaCOutput
    """
    generator = IaCGenerator(
        output_dir=output_dir,
        application_name=application_name,
        sources=sources,
        compute=compute,
        database=database,
        api=api,
        storage=storage,
        security=security
    )
    return generator.generate()
