# AWS Nuke with Step Functions

This solution implements AWS Nuke with a Step Function workflow that:
1. Generates an AWS Nuke configuration file excluding tagged resources and excluding CDK Toolkit and Control Tower resources
2. Runs AWS Nuke in dry-run mode to preview deletions
3. Waits for manual approval
4. Executes the actual cleanup

When this works correctly, you can redeploy the solution with a cron expression
to run it regularly. It will then directly start with nuking.

## Prerequisites

- AWS CLI configured ([download here](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- AWS CDK (Typescript) installed ([download here](https://docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-typescript.html))
- python3` and `pip` installed
- When you're running on Windows, install WSL ([download here](https://learn.microsoft.com/en-us/windows/wsl/install)) or Git bash  ([download here](https://git-scm.com/install/windows))

## Architecture

- Step Function orchestrates the workflow
- Lambda functions for creating the config file, run AWS Nuke execution and sending notifications
- S3 bucket for configuration files and logs
- SNS topic for sending mail

You can find more information about the architecture in
[my blog](https://conclusionxforce.cloud/blog/aws-nuke-based-on-tags/) on the
Conclusion Xforce Tech Playground.

## Deployment

### Configuration

First, copy the file `./setenv.template.sh` to `./setenv.sh` and configure this file. All configuration is in this file.

### Manual execution

I assume no-one will run aws-nuke on an account without wanting to know what it will clean. So, start with the manual deployment:

`bash ./scripts/deploy-cdk.sh`

This will get the Python and NodeJS files that you need for the deployment. If you didn't bootstrap CDK before, this will be done by the deployment script as well. It will also tag the bootstrapped resources with the correct tags. After that, it will start the deployment.

When the deployment is ready, you can start the workflow:

`bash ./scripts/start-manual-workflow.sh`

You will get an email when the dry-run is ready. In the email is a link to the S3 bucket where the output of the dry-run is stored. To make it more easy to decide what to do, only the resources that will be removed are shown. You can find the raw output of AWS Nuke in the S3 bucket if you want.

When you are convinced that nothing will go wrong, you can start removing the resources by approving the execution:

`bash ./scripts/approve-execution.sh`

It will now remove all resources that you saw in the dry run.

### Scheduled execution

When you are convinced that nothing will break, you can start the scheduled execution by changing the settings in `./setenv.sh` and running the script

`bash ./scripts/deploy-cdk.sh`

When you put a cron expression in the environment variable, this will deploy an EventBridge rule that will schedule the run for you. You will not get email for scheduled runs, you can look in the S3 bucket for the output of AWS Nuke.

## Warnings

* I used AI (AWS Kiro) for creating this solution. After a working release, I changed a lot to make the code better readable.

* When a new version of aws-nuke is released, this project will try to download and use it automatically. When that is not possible, it will fall back to the current version (on the moment of writing). You can change the fallback version in the `./setenv.sh`, but the code will always try to get the newest version. The idea behind this is that newer versions of AWS Nuke will remove more resources.

* All the warnings for aws-nuke apply to this solution as well: I don't give any guarantees for broken software, resources that are removed where they shouldn't etc. 
