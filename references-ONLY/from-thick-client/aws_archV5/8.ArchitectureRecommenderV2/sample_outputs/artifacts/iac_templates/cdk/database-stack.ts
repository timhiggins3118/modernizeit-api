import * as cdk from 'aws-cdk-lib';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

interface DatabaseStackProps extends cdk.StackProps {
  readonly vpc: cdk.aws_ec2.IVpc;
}

export class DatabaseStack extends cdk.Stack {
  public readonly database: rds.DatabaseInstance;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    // RDS PostgreSQL Instance
    this.database = new rds.DatabaseInstance(this, 'TestApp01Database', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_15,
      }),
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T4G,
        ec2.InstanceSize.MEDIUM
      ),
      vpc: props.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      multiAz: true,
      allocatedStorage: 100,
      maxAllocatedStorage: 200,
      databaseName: 'testapp01db',
      backupRetention: cdk.Duration.days(7),
      deleteAutomatedBackups: false,
      removalPolicy: cdk.RemovalPolicy.SNAPSHOT,
    });

    // Outputs
    new cdk.CfnOutput(this, 'DatabaseEndpoint', {
      value: this.database.dbInstanceEndpointAddress,
      description: 'Database Endpoint',
    });
  }
}
