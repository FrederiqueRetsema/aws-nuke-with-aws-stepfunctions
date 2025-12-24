import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import * as logs from 'aws-cdk-lib/aws-logs';

const runtime = lambda.Runtime.PYTHON_3_13

export interface AwsNukeStackProps extends cdk.StackProps {
  projectName: string;
  tagKey: string;
  tagValue: string;
  emailAddress: string;
  allowedRegions: string[];
  blocklistAccounts: string[];
  cdkBucketPrefix: string;
  scheduleExpression: string;
  bucketRetentionDays: number;
  logGroupRetentionDays: number;
  nukeVersion: string;
  enforceVersion: boolean;
}

export class AwsNukeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: AwsNukeStackProps) {
    super(scope, id, props);

    const { projectName, tagKey, tagValue, emailAddress, allowedRegions, blocklistAccounts, cdkBucketPrefix, scheduleExpression, bucketRetentionDays, logGroupRetentionDays, nukeVersion, enforceVersion} = props;

    const awsNukeBucketName = `${projectName}-aws-nuke-bucket-${this.account}`;

    const awsNukeBucket = new s3.Bucket(this, 'awsNukeBucket', {
      bucketName: awsNukeBucketName,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [{
          id: 'DeletionRule',
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(bucketRetentionDays),
          expiration: cdk.Duration.days(bucketRetentionDays),
      }]
    });

    const notificationTopic = new sns.Topic(this, 'NukeNotificationTopic', {
      topicName: `${projectName}-nuke-notifications`,
      displayName: 'AWS Nuke Execution Notifications',
    });

    notificationTopic.addSubscription(
      new subscriptions.EmailSubscription(emailAddress)
    );

    const generateConfigFunction = new lambda.Function(this, 'GenerateConfigFunction', {
      functionName: `${projectName}-generate-config`,
      runtime: runtime,
      handler: 'generate_config.lambda_handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
    });

    generateConfigFunction.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        's3:PutObject',
      ],
      resources: [
        `${awsNukeBucket.bucketArn}/*`,
      ],
    }));

    const logGroupGenerateConfigFunction = new logs.LogGroup(this, 'LogGroupGenerateConfigFunction', {
      logGroupName: `/aws/lambda/${projectName}-generate-config`,
      retention: logGroupRetentionDays,
    })

    const nukeExecutorFunction = new lambda.Function(this, 'NukeExecutorFunction', {
      functionName: `${projectName}-nuke-executor`,
      runtime: runtime,
      handler: 'nuke_executor.lambda_handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(15),
      memorySize: 1024,
      environment: {
        TAG_KEY: tagKey,
        TAG_VALUE: tagValue,
      },
    });

    nukeExecutorFunction.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['*'],
      resources: ['*'],
    }));

    nukeExecutorFunction.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        's3:GetObject',
        's3:PutObject',
        's3:DeleteObject',
        's3:ListBucket',
      ],
      resources: [
        awsNukeBucket.bucketArn,
        `${awsNukeBucket.bucketArn}/*`,
      ],
    }));

    const logGroupExecutorFunction = new logs.LogGroup(this, 'LogGroupNukeExecutorFunction', {
      logGroupName: `/aws/lambda/${projectName}-nuke-executor`,
      retention: logGroupRetentionDays,
    })

    const sendNotificationFunction = new lambda.Function(this, 'SendNotificationFunction', {
      functionName: `${projectName}-send-notification`,
      runtime: runtime,
      handler: 'send_notification.lambda_handler',
      code: lambda.Code.fromAsset('../lambda'),
      timeout: cdk.Duration.minutes(1),
      memorySize: 256,
      environment: {
        NOTIFICATION_TOPIC_ARN: notificationTopic.topicArn,
      },
    });

    notificationTopic.grantPublish(sendNotificationFunction);

    sendNotificationFunction.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        's3:GetObject',
        's3:ListBucket',
      ],
      resources: [
        awsNukeBucket.bucketArn,
        `${awsNukeBucket.bucketArn}/*`,
      ],
    }));

    const logGroupSendNotification = new logs.LogGroup(this, 'LogGroupSendNotification', {
      logGroupName: `/aws/lambda/${projectName}-send-notification`,
      retention: logGroupRetentionDays,
    })

    // Step Function tasks
    const generateConfig = new tasks.LambdaInvoke(this, 'GenerateConfig', {
      lambdaFunction: generateConfigFunction,
      payload: sfn.TaskInput.fromObject({
        'AccountId.$': '$$.Execution.Input.AccountId',
        'Regions.$': '$$.Execution.Input.Regions',
        'awsNukeBucket.$': '$$.Execution.Input.awsNukeBucket',
        'cdkBucketPrefix.$': '$$.Execution.Input.cdkBucketPrefix',
        'TagKey': tagKey,
        'TagValue': tagValue,
        'BlocklistAccounts': blocklistAccounts,
        'ProjectName': projectName,
      }),
      outputPath: '$.Payload',
    });

    const runNuke = new tasks.LambdaInvoke(this, 'RunNuke', {
      lambdaFunction: nukeExecutorFunction,
      payload: sfn.TaskInput.fromObject({
        'ConfigS3Uri.$': '$.ConfigS3Uri',
        'AccountId.$': '$$.Execution.Input.AccountId',
        'DryRun.$': '$$.Execution.Input.DryRun',
        'NukeVersion': nukeVersion,
        'EnforceVersion': enforceVersion,
        'SendNotification.$': '$$.Execution.Input.SendNotification',
      }),
      outputPath: '$.Payload',
    });

    const sendNotification = new tasks.LambdaInvoke(this, 'SendNotification', {
      lambdaFunction: sendNotificationFunction,
      payload: sfn.TaskInput.fromObject({
        'ExecutionId.$': '$$.Execution.Name',
        'StateMachineArn.$': '$$.StateMachine.Id',
        'ExecutionType': 'EXECUTION_COMPLETE',
        'OutputS3Uri.$': '$.OutputS3Uri',
        'ResourcesToDelete.$': '$.ResourcesToDelete',
        'Success.$': '$.Success',
        'DryRun.$': '$$.Execution.Input.DryRun',
        'SendNotification.$': '$$.Execution.Input.SendNotification',
      }),
    });

    const completed = new sfn.Succeed(this, 'Completed');
    const failed = new sfn.Fail(this, 'Failed');

    generateConfig.addCatch(failed, {
      errors: ['States.ALL'],
      resultPath: '$.error',
    });

    runNuke.addCatch(failed, {
      errors: ['States.ALL'],
      resultPath: '$.error',
    });

    const checkNotification = new sfn.Choice(this, 'CheckNotification')
      .when(
        sfn.Condition.booleanEquals('$.SendNotification', false),
        completed
      )
      .otherwise(sendNotification.next(completed));

    const definition = generateConfig
      .next(runNuke)
      .next(checkNotification);

    const stateMachine = new sfn.StateMachine(this, 'NukeWorkflow', {
      stateMachineName: `${projectName}-nuke-workflow`,
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      timeout: cdk.Duration.hours(2),
    });

    generateConfigFunction.grantInvoke(stateMachine);
    nukeExecutorFunction.grantInvoke(stateMachine);
    sendNotificationFunction.grantInvoke(stateMachine);

    if (scheduleExpression != 'manual') {
      
      const scheduleRule = new events.Rule(this, 'NukeScheduleRule', {
        ruleName: `${projectName}-nuke-schedule`,
        description: `Scheduled execution of AWS Nuke workflow: ${scheduleExpression}`,
        schedule: events.Schedule.expression(props.scheduleExpression),
        enabled: true,
      });

      scheduleRule.addTarget(new targets.SfnStateMachine(stateMachine, {
        input: events.RuleTargetInput.fromObject({
          awsNukeBucket: awsNukeBucketName,
          AccountId: this.account,
          Regions: allowedRegions,
          DryRun: false, // Scheduled executions run actual deletion (no approval)
          NukeVersion: nukeVersion,
          EnforceVersion: enforceVersion,
          ScheduledExecution: true,
          SendNotification: false, // No email notifications for scheduled executions
        }),
      }));

      new cdk.CfnOutput(this, 'ScheduleRuleArn', {
        value: scheduleRule.ruleArn,
        description: `EventBridge rule ARN for scheduled execution (${props.scheduleExpression})`,
      });
    }

    // Outputs
    new cdk.CfnOutput(this, 'StateMachineArn', {
      value: stateMachine.stateMachineArn,
      description: 'ARN of the Step Function state machine',
    });

    new cdk.CfnOutput(this, 'NotificationTopicArn', {
      value: notificationTopic.topicArn,
      description: 'ARN of the SNS notification topic',
    });

    new cdk.CfnOutput(this, 'awsNukeBucketName', {
      value: awsNukeBucketName,
      description: `S3 bucket for AWS Nuke configurations (${bucketRetentionDays} days retention)`,
    });

  }
}
