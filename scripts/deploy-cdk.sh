#!/bin/bash

function install_lambda_dependencies {
   echo "Installing Lambda Dependencies..."

   cd lambda

   echo "Cleaning existing YAML directories..."
   rm -rf yaml _yaml __pycache__

   echo "Creating temporary virtual environment..."
   python3 -m venv temp_venv
   source temp_venv/bin/activate

   echo "Installing PyYAML..."
   pip install pyyaml>=6.0

   echo "Copying PyYAML to lambda directory..."
   SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")

   if [ -d "$SITE_PACKAGES/yaml" ]; then
      cp -r "$SITE_PACKAGES/yaml" .
      echo "✅ Copied yaml directory"
   else
      echo "❌ yaml directory not found in site-packages"
   fi

   if [ -d "$SITE_PACKAGES/_yaml" ]; then
      cp -r "$SITE_PACKAGES/_yaml" .
      echo "✅ Copied _yaml directory"
   else
      echo "⚠️  _yaml directory not found (this is optional)"
   fi

   find "$SITE_PACKAGES" -name "*yaml*.so" -exec cp {} . \; 2>/dev/null || true

   # Cleanup
   deactivate
   rm -rf temp_venv

   echo ""
   echo "✅ Lambda dependencies installation complete!"
   cd ..
}

function install_nodejs_dependencies {
   # Navigate to CDK directory
   cd cdk

   # Install dependencies
   echo "Installing dependencies..."
   if test -d ./node_modules
   then
      rm -fr ./node_modules
   fi
   npm install

   # Build TypeScript
   echo "Building TypeScript..."
   rm -rf lib/lib lib/bin
   npm run build 
   cd ..
}

function install_cdk_dependencies {
   cd cdk

   echo "Checking CDK bootstrap..."
   AWS_PROFILE="$PROFILE" cdk bootstrap --tags "${TAG_KEY}"="${TAG_VALUE}" || true

   cd ..
}

# Deploy AWS Nuke infrastructure using CDK
set -e

echo "AWS Nuke CDK Deployment Script"
echo "==============================="
echo ""

# Set defaults
if test -f ./setenv.sh
then
  . ./setenv.sh
else
  echo "❌ ./setenv.sh not found. Copy setenv.template.sh to setenv.sh and change the contents."
  exit 1
fi

install_lambda_dependencies
install_nodejs_dependencies
install_cdk_dependencies

if [ "${SCHEDULE}" = "manual" ]; then
   echo "Mode: Manual execution with dry-run and approval steps"
elif [ -n "${SCHEDULE}" ]; then
   echo "Mode: Scheduled execution with cron expression: ${SCHEDULE}"
fi
echo ""

cd cdk
echo "Deploying stack..."
AWS_PROFILE="${PROFILE}" cdk deploy \
 -c tagKey="${TAG_KEY}" \
 -c tagValue="${TAG_VALUE}" \
 -c emailAddress="${EMAIL_ADDRESS}" \
 -c regions="${REGIONS}" \
 -c deploymentMode="${DEPLOYMENT_MODE}" \
 -c blocklistAccounts="${BLOCKLIST_ACCOUNTS}" \
 -c cdkBucketPrefix="${CDK_BUCKET_PREFIX}" \
 -c scheduleExpression="${SCHEDULE}" \
 -c bucketRetentionDays="${BUCKET_RETENTION_DAYS}" \
 -c logGroupRetentionDays="${LOG_GROUP_RETENTION_DAYS}" \
 -c nukeVersion="${NUKE_VERSION}" \
 -c enforceVersion="${ENFORCE_VERSION}" \
  --tags "${TAG_KEY}"="${TAG_VALUE}" \
  --require-approval never

echo ""
echo "Deployment complete!"

echo ""
echo "Don't forget to confirm the SNS subscription in your email."
cd ..
