#!/bin/bash

# Script to start the AWS Nuke manual workflow (with dry-run and approval)
# Usage: ./start-manual-workflow.sh

set -e

. ./setenv.sh

# Get Step Function ARN (look for the nuke-workflow)
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
    --query "stateMachines[?contains(name, 'nuke-workflow')].stateMachineArn | [0]" \
    --output text \
    --profile "$PROFILE")

if [ -z "$STATE_MACHINE_ARN" ] || [ "$STATE_MACHINE_ARN" = "None" ]; then
    echo "Error: AWS Nuke Step Function not found."
    echo "Available state machines:"
    aws stepfunctions list-state-machines \
        --query "stateMachines[].name" \
        --output table \
        --profile "$PROFILE" 2>/dev/null || echo "  (Unable to list state machines)"
    echo ""
    echo "Deploy with: SCHEDULE=manual ./scripts/deploy-cdk.sh"
    exit 1
fi

echo "Starting AWS Nuke MANUAL workflow..."
echo "This workflow includes dry-run and approval steps."
echo ""
echo "AWS Profile: $PROFILE"
echo "State Machine: $STATE_MACHINE_ARN"
echo "Account ID: $ACCOUNT_ID"
echo "Config Bucket: $AWS_NUKE_BUCKET"
echo "Regions: $ALLOWED_REGIONS"
echo ""

# Start execution
EXECUTION_ARN=$(aws stepfunctions start-execution \
    --state-machine-arn "$STATE_MACHINE_ARN" \
    --input "{
        \"awsNukeBucket\": \"$AWS_NUKE_BUCKET\",
        \"cdkBucketPrefix\": \"$CDK_BUCKET_PREFIX\",
        \"AccountId\": \"$ACCOUNT_ID\",
        \"Regions\": [$(echo $ALLOWED_REGIONS | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/')],
        \"DryRun\": true,
        \"SendNotification\": true
    }" \
    --query 'executionArn' \
    --output text \
    --profile "$PROFILE")

echo "Manual workflow started successfully!"
echo "Execution ARN: $EXECUTION_ARN"
echo ""
echo "Workflow steps:"
echo "1. Scan protected resources"
echo "2. Generate AWS Nuke configuration"
echo "3. Run dry-run (no actual deletion)"
echo "4. Send email with dry-run results"
echo "5. Wait up to 24 hours for approval"
echo "6. If approved: execute actual cleanup"
echo "7. Send final notification"
echo ""
echo "Monitor execution:"
echo "aws stepfunctions describe-execution --execution-arn $EXECUTION_ARN --profile $PROFILE"
echo ""
echo "Check your email for dry-run results and approval instructions."