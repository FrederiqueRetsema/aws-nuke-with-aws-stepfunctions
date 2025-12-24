import json
import boto3
import os
from typing import Dict, Any
from urllib.parse import urlparse

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Send notifications for both dry-run approval and final execution results.
    """
    sns = boto3.client('sns')
    s3 = boto3.client('s3')

    topic_arn = os.environ.get('NOTIFICATION_TOPIC_ARN', os.environ.get('APPROVAL_TOPIC_ARN', ''))
    execution_id = event.get('ExecutionId', 'Unknown')
    execution_arn = event.get('ExecutionArn', '')
    state_machine_arn = event.get('StateMachineArn', '')
    dry_run_mode = event.get('DryRun', False)

    # If we don't have the full ARN, construct it from the state machine ARN and execution ID
    if not execution_arn and execution_id != 'Unknown' and state_machine_arn:
        # Convert state machine ARN to execution ARN
        # arn:aws:states:region:account:stateMachine:name -> arn:aws:states:region:account:execution:name:execution-id
        execution_arn = state_machine_arn.replace(':stateMachine:', ':execution:') + ':' + execution_id
    elif not execution_arn and execution_id != 'Unknown':
        # Fallback: construct from topic ARN if available
        if topic_arn:
            # Parse topic ARN: arn:aws:sns:region:account:topic-name
            arn_parts = topic_arn.split(':')
            if len(arn_parts) >= 5:
                region = arn_parts[3]
                account = arn_parts[4]
                execution_arn = f"arn:aws:states:{region}:{account}:execution:aws-nuke-nuke-workflow:{execution_id}"
    
    print(f"Environment variables: {dict(os.environ)}")
    print(f"Topic ARN: {topic_arn}")
    print(f"Execution ID: {execution_id}")
    print(f"Execution ARN: {execution_arn}")
    print(f"Dry run: {dry_run_mode}")

    if not topic_arn:
        print("ERROR: No SNS topic ARN found in environment variables")
        return {
            'Success': False,
            'Error': 'No SNS topic ARN configured'
        }
    
    presigned_url = 'N/A'
    output_s3_uri = event.get('OutputS3Uri', 'N/A')
    
    execution_result = event.get('ExecutionResult', {})
    
    print(f"Full execution result: {json.dumps(execution_result, default=str)}")
    
    resources_deleted = event.get('ResourcesToDelete', execution_result.get('ResourcesToDelete', 0))
    success = event.get('Success', execution_result.get('Success', False))
    output_s3_uri = event.get('OutputS3Uri', execution_result.get('OutputS3Uri', 'N/A'))
    error_message = execution_result.get('Error', '')
    
    # Generate presigned URL for results
    if output_s3_uri and output_s3_uri.startswith('s3://'):
        try:
            seven_days_in_seconds = 7 * 24 * 60 * 60
            parsed = urlparse(output_s3_uri)
            bucket = parsed.netloc
            key = parsed.path.lstrip('/')
            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=seven_days_in_seconds
            )
        except Exception as e:
            presigned_url = f'Error generating URL: {str(e)}'

    if dry_run_mode:
        subject = f'🔍 AWS Nuke DRY-RUN Results - {resources_deleted} resources found - APPROVAL REQUIRED'        
        message = f"""🔍 AWS Nuke DRY-RUN Results - APPROVAL REQUIRED

Execution ID: {execution_id}
Execution ARN: {execution_arn}
Type: DRY-RUN (No resources were actually deleted)

Summary:
- Resources that WOULD BE DELETED: {resources_deleted}

⚠️  CRITICAL: Please review the dry-run results carefully before approving!

Dry-Run Results:
{presigned_url if presigned_url != 'N/A' else 'No output file available'}

{f'(Link valid for 7 days)' if presigned_url != 'N/A' else ''}

S3 Location: {output_s3_uri}

🚨 SAFETY CHECK - Before approving, verify that:
✅ No critical resources are listed for deletion
✅ The AwsNukeStack itself is NOT in the deletion list
✅ CDK bootstrap resources are protected
✅ All important resources have the 'Cleanup: persist' tag

📋 APPROVAL INSTRUCTIONS:

TO APPROVE (proceed with actual deletion):
# Review the dry-run results above thoroughly, then run:

./scripts/approve-execution.sh

- The approval script will start a NEW execution that performs actual deletion
- You'll receive another email when the actual execution completes

TO REJECT (do nothing):
# Simply don't run the approval script - no resources will be deleted
"""
        
        try:
            print(f"Sending notification to topic: {topic_arn}")
            print(f"Subject: {subject}")
            print(f"Message length: {len(message)}")
            
            response = sns.publish(
                TopicArn=topic_arn,
                Subject=subject,
                Message=message
            )
            
            print(f"SNS publish successful. MessageId: {response['MessageId']}")
            return {
                'MessageId': response['MessageId'],
                'Success': True,
                'PresignedUrl': presigned_url
            }
        except Exception as e:
            print(f"ERROR sending SNS notification: {str(e)}")
            return {
                'Success': False,
                'Error': f'Failed to send notification: {str(e)}',
                'PresignedUrl': presigned_url
            }
    
    else:
        subject = f'✅ AWS Nuke Execution Complete - {resources_deleted} resources processed'
        message = f"""✅ AWS Nuke Execution Complete

Execution ID: {execution_id}
Execution ARN: {execution_arn}

Summary:
- Resources Processed: {resources_deleted}

Final Execution Results (Full Output):
{presigned_url if presigned_url != 'N/A' else 'No output file available'}

{f'(Link valid for 7 days)' if presigned_url != 'N/A' else ''}

S3 Location: {output_s3_uri}

The AWS Nuke execution has completed. Please review the results above.

🔗 Monitor future executions:
To run AWS Nuke again, use: ./scripts/start-manual-workflow.sh

"""
    
    try:
        print(f"Sending notification to topic: {topic_arn}")
        print(f"Subject: {subject}")
        print(f"Message length: {len(message)}")
        
        response = sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        
        print(f"SNS publish successful. MessageId: {response['MessageId']}")
        
        return {
            'MessageId': response['MessageId'],
            'Success': True,
            'PresignedUrl': presigned_url
        }
    except Exception as e:
        print(f"ERROR sending SNS notification: {str(e)}")
        return {
            'Success': False,
            'Error': f'Failed to send notification: {str(e)}',
            'PresignedUrl': presigned_url
        }
