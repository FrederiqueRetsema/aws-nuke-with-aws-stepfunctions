
#!/bin/bash

# Simple approval script for AWS Nuke
# This starts a new execution that performs actual resource deletion
set -e

. ./setenv.sh

# Get Step Function ARN
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
    --query "stateMachines[?contains(name, 'nuke-workflow')].stateMachineArn | [0]" \
    --output text \
    --profile "$PROFILE")

if [ -z "$STATE_MACHINE_ARN" ] || [ "$STATE_MACHINE_ARN" = "None" ]; then
    echo "Error: AWS Nuke Step Function not found."
    echo "Deploy with: ./scripts/deploy-manual.sh"
    exit 1
fi

echo "State Machine: $STATE_MACHINE_ARN"
echo ""

# Start execution with actual deletion (no dry-run)
EXECUTION_ARN=$(aws stepfunctions start-execution \
    --state-machine-arn "$STATE_MACHINE_ARN" \
    --input "{
        \"awsNukeBucket\": \"$AWS_NUKE_BUCKET\",
        \"cdkBucketPrefix\": \"$CDK_BUCKET_PREFIX\",
        \"AccountId\": \"$ACCOUNT_ID\",
        \"Regions\": [$(echo $ALLOWED_REGIONS | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/')],
        \"DryRun\": false,
        \"SendNotification\": true
    }" \
    --query 'executionArn' \
    --output text \
    --profile "$PROFILE")

echo "✅ Actual execution started successfully!"
echo "Execution ARN: $EXECUTION_ARN"
echo ""
echo "You will receive an email notification when the execution completes."
