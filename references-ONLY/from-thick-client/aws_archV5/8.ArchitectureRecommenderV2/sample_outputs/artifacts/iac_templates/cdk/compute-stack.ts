import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Construct } from 'constructs';

interface ComputeStackProps extends cdk.StackProps {
  readonly vpc: cdk.aws_ec2.IVpc;
  readonly lambdaExecutionRole: cdk.aws_iam.IRole;
}

export class ComputeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    // Lambda Function: BatchProcessor
    const batchprocessor = new lambda.Function(this, 'BatchProcessor', {
      runtime: lambda.Runtime.JAVA_17,
      handler: 'com.example.BatchProcessor::handleRequest',
      code: lambda.Code.fromAsset('lambda/batchprocessor'),
      memorySize: 1024,
      timeout: cdk.Duration.seconds(900),
      role: props.lambdaExecutionRole,
      vpc: props.vpc,
    });

    // CloudWatch Events Rule (example - daily at 2 AM)
    const rule = new events.Rule(this, 'DailyTrigger', {
      schedule: events.Schedule.cron({ hour: '2', minute: '0' }),
    });

    // NOTE: Add more Lambda functions and triggers as needed
  }
}
