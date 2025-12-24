#!bin/bash

PROFILE="default"
TAG_KEY="Cleanup"
TAG_VALUE="persist"
REGIONS="eu-west-1,eu-central-1"
EMAIL_ADDRESS="xforce@example.com"
SCHEDULE="manual" # Or cron expression, f.e. cron(0 4 * * ? *) to run every night at 4:00
BUCKET_RETENTION_DAYS="30"
LOG_GROUP_RETENTION_DAYS="14"
CDK_BUCKET_PREFIX="cdk" # Will always work, cdk-abc123def might be more specific. See the S3 console for your prefix.
BLOCKLIST_ACCOUNTS="123456789012"

NUKE_VERSION="v3.62.2"
ENFORCE_VERSION="false" # true means: always use the ${NUKE_VERSION},
                        # false means: always try to use the latest version - fallback to ${NUKE_VERSION} if the new version cannot be determined

PROJECT_NAME="aws-nuke"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile "${PROFILE}")
AWS_NUKE_BUCKET="${PROJECT_NAME}-aws-nuke-bucket-${ACCOUNT_ID}"

