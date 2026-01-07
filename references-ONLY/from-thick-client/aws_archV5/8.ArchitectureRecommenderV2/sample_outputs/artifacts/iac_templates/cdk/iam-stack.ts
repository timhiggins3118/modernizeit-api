import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class IamStack extends cdk.Stack {
  public readonly lambdaExecutionRole: iam.Role;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Lambda Execution Role
    this.lambdaExecutionRole = new iam.Role(this, 'LambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaVPCAccessExecutionRole'),
      ],
    });

    // Add RDS access permissions
    this.lambdaExecutionRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'rds-data:ExecuteStatement',
        'rds-data:BatchExecuteStatement',
      ],
      resources: ['*'],
    }));

    // Add S3 access permissions
    this.lambdaExecutionRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        's3:GetObject',
        's3:PutObject',
      ],
      resources: ['arn:aws:s3:::testapp01-*/*'],
    }));

    // Outputs
    new cdk.CfnOutput(this, 'LambdaExecutionRoleArn', {
      value: this.lambdaExecutionRole.roleArn,
      description: 'Lambda Execution Role ARN',
    });
  }
}
