#!bin/bash

PROFILE="default"
TAG_KEY="Cleanup"
TAG_VALUE="persist"
ALLOWED_REGIONS="eu-west-1,eu-central-1"
EMAIL_ADDRESS="xforce@example.com"
SCHEDULE="manual" # Or cron expression, f.e. cron(0 4 * * ? *) to run every night at 4:00
RETENTION_DAYS="30"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile "$PROFILE")
CDK_BUCKET_PREFIX="cdk-abc123def"
BLOCKLIST_ACCOUNTS="123456789012"

PROJECT_NAME="aws-nuke"
AWS_NUKE_BUCKET="${PROJECT_NAME}-aws-nuke-bucket-${ACCOUNT_ID}"

NUKE_VERSION="v3.62.2"
ENFORCE_VERSION="false" # true means: always use the ${NUKE_VERSION},
                        # false means: always try to use the latest version - fallback to ${NUKE_VERSION} if the new version cannot be determined