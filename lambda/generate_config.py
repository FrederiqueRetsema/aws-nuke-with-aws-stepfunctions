import json
import boto3
import yaml
from datetime import datetime
from typing import Dict, Any, List

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate AWS Nuke configuration file with protected resources.
    Upload the config to S3 bucket.
    """
    account_id = event['AccountId']
    regions = event['Regions']
    aws_nuke_bucket = event['awsNukeBucket']
    cdk_bucket_prefix = event['cdkBucketPrefix']
    tag_key = event['TagKey']
    tag_value = event['TagValue']
    blocklist_accounts = event.get('BlocklistAccounts')
    project_prefix = event.get('ProjectName')
    
    nuke_config = {
        'regions': regions,
        'blocklist': blocklist_accounts,
        'resource-types': {
            'excludes': [
                # Network interfaces and attachments (removed with parent resources)
                'EC2NetworkInterface',
                'EC2DHCPOption', 
                'EC2InternetGatewayAttachment',
                
                # Bedrock issues
                'BedrockModelCustomizationJob',
                
                # Deprecated/unused resource types
                'CloudSearchDomain',
                'CodeStarProject',
                'ElasticTranscoder*',
                'FMSNotificationChannel',
                'FMSPolicy',
                'OpsWorks*',
                'QLDBLedger',
                'Lex*',
                'MachineLearning*',
                'RoboMaker*',
                'ShieldProtection*',
                'AWS::Timestream::*'

                # Add ServiceCatalogTagOption and ServiceCatalogTagOptionPortfolioAttachment
                # when you don't use ServiceCatalog tag options
                # to get rid of the "TagOption: Migration not complete" info message
            ]
        },
        'accounts': {
            account_id: {
                'filters': {
                    '__global__': [
                        {
                            'property': f'tag:{tag_key}',
                            'value': tag_value
                        },
                        {
                            'property': 'tag:aws:cloudformation:stack-name',
                            'value': 'CDKToolkit'
                        },
                        {
                            'property': 'tag:aws:cloudformation:stack-name',
                            'type': 'glob',
                            'value': 'StackSet-AWSControlTowerBP-*'
                        },
                        {
                            'property': 'Name',
                            'type': 'glob',
                            'value': 'aws-controltower-*'
                        },
                        {
                            'property': 'Name',
                            'type': 'glob',
                            'value': 'AWSControlTower*'
                        },
                        {
                            'property': 'Name',
                            'type': 'glob',
                            'value': f'{project_prefix}*'
                        }
                    ],
                    'S3Object': [
                        {
                            'property': 'Bucket',
                            'value': aws_nuke_bucket
                        },
                        {
                            'property': 'Bucket',
                            'type': 'glob',
                            'value': f'{cdk_bucket_prefix}-*'
                        }
                    ],
                    'SNSTopic': [
                        {
                            'property': 'TopicARN',
                            'type': 'glob',
                            'value': f'arn:aws:sns:*:{account_id}:aws-controltower-*'
                        }
                    ],
                    'SNSSubscription': [
                        {
                            'property': 'TopicARN',
                            'type': 'glob',
                            'value': f'arn:aws:sns:*:{account_id}:{project_prefix}-*'
                        },
                        {
                            'property': 'TopicARN',
                            'type': 'glob',
                            'value': f'arn:aws:sns:*:{account_id}:aws-controltower-*'
                        }
                    ],
                    'CloudWatchLogsLogGroup': [
                        {
                            'property': 'Name',
                            'type': 'glob',
                            'value': f'/aws/lambda/{project_prefix}-*'
                        },
                        {
                            'property': 'Name',
                            'type': 'glob',
                            'value': f'/aws/lambda/aws-controltower-*'
                        }
                    ],
                    'CloudFormationStack': [
                        {
                            'property': 'Name',
                            'type': 'glob',
                            'value': 'StackSet-AWSControlTowerBP-*'
                        }
                    ]
                }
            }
        }
    }
    
    config_yaml = yaml.dump(nuke_config, default_flow_style=False)
        
    s3 = boto3.client('s3')
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    config_key = f"nuke-configs/nuke-config-{timestamp}.yaml"
    
    s3.put_object(
        Bucket=aws_nuke_bucket,
        Key=config_key,
        Body=config_yaml,
        ContentType='application/x-yaml'
    )
    
    aws_nuke_s3_uri = f"s3://{aws_nuke_bucket}/{config_key}"
    
    print(f"Generated AWS Nuke config for project: {project_prefix}")
    print(f"Config uploaded to: {aws_nuke_s3_uri}")
    
    return {
        'ConfigFileKey': config_key,
        'ConfigS3Uri': aws_nuke_s3_uri,
        'ConfigContent': config_yaml
    }