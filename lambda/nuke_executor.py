import json
import boto3
import subprocess
import os
import urllib.request
import urllib.error
import tarfile
import tempfile
from datetime import datetime
from typing import Dict, Any

s3 = boto3.client('s3')


def parse_event(event) -> (str, bool, str, bool, str, bool):

    print(f"Lambda event: {json.dumps(event, default=str)}")

    aws_nuke_s3_uri = event['ConfigS3Uri']
    dry_run = event.get('DryRun', True)
    account_id = event['AccountId']
    send_notification = event.get('SendNotification', True)
    nuke_version = event.get('NukeVersion')
    enforce_version = event.get('EnforceVersion')
    
    print(f"DryRun parameter: {dry_run}")
    print(f"SendNotification parameter: {send_notification}")

    return aws_nuke_s3_uri, dry_run, account_id, send_notification, nuke_version, enforce_version


def store_in_s3(bucket: str, key: str, body: str) -> str:

    output_s3_uri = ""
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType='text/plain'
        )
        output_s3_uri = f"s3://{bucket}/{key}"
    except Exception as s3_error:
        print(f"Failed to upload full output to S3: {s3_error}")
        output_s3_uri = f"s3://{bucket}/{key} (upload failed)"

    return output_s3_uri


def download_config_file(aws_nuke_s3_uri):
    
    # Example of s3 uri: s3://bucketname/key
    bucket = aws_nuke_s3_uri.split('/')[2]
    key = '/'.join(aws_nuke_s3_uri.split('/')[3:])
    config_path = '/tmp/nuke-config.yaml'

    print(f"Bucket: {bucket}, key: {key}")
    print(f"Config path: {config_path}")

    s3.download_file(bucket, key, config_path)

    return config_path


def determine_version(nuke_version: str, enforce_version: bool) -> str:

    version_to_use = nuke_version
    print(f"AWS Nuke version: {version_to_use}")

    if (not enforce_version):
        try:
            print("Attempting to fetch latest AWS Nuke version from GitHub...")
            request = urllib.request.Request(
                'https://api.github.com/repos/ekristen/aws-nuke/releases/latest',
                headers={
                    'User-Agent': 'AWS-Nuke-Lambda-Executor/1.0',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.getcode() == 200:
                    release_data = json.loads(response.read().decode())
                    fetched_version = release_data['tag_name']
                    print(f"Latest version available: {fetched_version}")
                    # Only use if it's newer than our fallback
                    if fetched_version >= version_to_use:
                        version_to_use = fetched_version
                        print(f"Using latest version: {version_to_use}")
                else:
                    print(f"GitHub API returned status {response.getcode()}, using fallback")
        except Exception as e:
            print(f"Could not fetch latest version: {e}, using fallback {version_to_use}")

    return version_to_use


def log_aws_nuke_version(nuke_binary_path: str):

    print("Get aws-nuke version...")
    version_result = subprocess.run([nuke_binary_path, '--version'], 
                                    capture_output=True, text=True, timeout=10)
    version_info = version_result.stdout.strip() or version_result.stderr.strip()
    print(f"AWS Nuke version: {version_info}")


def find_binary_in_tarfile(nuke_binary_path: str, tar: tarfile, members: str) -> str:

    for member in members:
        if 'aws-nuke' in member.name:
            print(f"Found potential binary: {member.name} ({member.size} bytes)")

            print(f"Extracting {member.name} to /tmp")
            tar.extract(member, '/tmp')
            
            extracted_path = os.path.join('/tmp', member.name)
            print(f"Extracted to: {extracted_path}")
            
            if extracted_path != nuke_binary_path:
                print(f"Renaming {extracted_path} to {nuke_binary_path}")
                os.rename(extracted_path, nuke_binary_path)
            
            print(f"Making {nuke_binary_path} executable")
            os.chmod(nuke_binary_path, 0o755)
            
            if os.path.exists(nuke_binary_path):
                if os.access(nuke_binary_path, os.X_OK):
                    try:
                        log_aws_nuke_version(nuke_binary_path)
                        print(f"Nuke binary path: {nuke_binary_path}")
                        
                        return nuke_binary_path
                        
                    except Exception as version_error:
                        print(f"Version/help check failed: {version_error}")
                        # Continue trying other files
                else:
                    print("Binary is not executable")
            else:
                print("Binary does not exist after extraction")

    raise Exception(f"No executable aws-nuke binary found in archive. Archive contained {len(members)} files.")


def extract(tar_path: str, nuke_binary_path: str) -> str:

    print(f"Extracting tar file: {tar_path}")
    with tarfile.open(tar_path, 'r:gz') as tar:
        members = tar.getmembers()
        print(f"Archive contains {len(members)} files:")
        for member in members[:10]:
            print(f"  - {member.name} ({member.size} bytes)")
        
        nuke_binary_path = find_binary_in_tarfile(nuke_binary_path, tar, members)
        return nuke_binary_path


def download_aws_nuke(nuke_version: str, enforce_version: bool) -> str:
    """
    Download AWS Nuke binary to /tmp and return the path.
    """
    nuke_binary_path = '/tmp/aws-nuke'
    
    if os.path.exists(nuke_binary_path) and os.access(nuke_binary_path, os.X_OK):
        print("AWS Nuke binary already exists in /tmp")
        log_aws_nuke_version(nuke_binary_path)

        return nuke_binary_path
    
    version_to_use = determine_version(nuke_version, enforce_version)

    download_url = f"https://github.com/ekristen/aws-nuke/releases/download/{version_to_use}/aws-nuke-{version_to_use}-linux-amd64.tar.gz"
    print(f"Downloading from: {download_url}")
    
    try:
        tar_path = '/tmp/aws-nuke.tar.gz'
        
        request = urllib.request.Request(
            download_url,
            headers={'User-Agent': 'AWS-Nuke-Lambda-Executor/1.0'}
        )
        
        print(f"Starting download from {download_url}")
        with urllib.request.urlopen(request, timeout=60) as download_response:
            if download_response.getcode() != 200:
                raise Exception(f"Download failed with status code: {download_response.getcode()}")
            
            download_content = download_response.read()
            print(f"Downloaded {len(download_content)} bytes")
            
            if len(download_content) == 0:
                raise Exception("Downloaded file is empty")
            
            with open(tar_path, 'wb') as f:
                f.write(download_content)
        
        print(f"Saved tar.gz file: {os.path.getsize(tar_path)} bytes")
        
        extract(tar_path, nuke_binary_path)

    except Exception as e:
        print(f"Failed to download AWS Nuke: {e}")
        raise Exception(f"Could not download AWS Nuke binary: {e}")

    return nuke_binary_path


def execute_nuke(nuke_binary: str, config_path: str, dry_run: bool) -> str:

    print(f"Nuke binary: {nuke_binary}")
    print(f"Config path: {config_path}")
    print(f"Dry run: {dry_run}")

    cmd = [nuke_binary, 'run']
    
    cmd.extend(['--config', config_path])
    cmd.extend(['--no-prompt'])
    
    if not dry_run:
        cmd.append('--no-dry-run')
        print("EXECUTION MODE")
    else:
        print("DRY-RUN MODE")
        
    print(f"Executing command: {' '.join(cmd)}")
    print(f"Timeout set to: 14.5 minutes")
    print(f"Dry run mode: {dry_run}")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=870 # 14.5 minute, a little bit less than Lambda's 15 minute limit
    )

    return result



def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Execute AWS Nuke with the generated configuration.
    Downloads AWS Nuke binary at runtime to avoid layer size limits.
    """

    aws_nuke_s3_uri, dry_run, account_id, send_notification, nuke_version, enforce_version = parse_event(event)    
    bucket = aws_nuke_s3_uri.split('/')[2]

    config_path = download_config_file(aws_nuke_s3_uri)

    # Download AWS Nuke binary
    try:
        nuke_binary = download_aws_nuke(nuke_version, enforce_version)
    except Exception as e:
        # If download fails, return error
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        error_output = f"Failed to download AWS Nuke binary: {str(e)}\n"
        error_output += f"This may be due to network issues or GitHub rate limiting.\n"
        
        output_key = f"nuke-outputs/nuke-error-{timestamp}-download-failed.txt"
        print(f"Error: {error_output}")
        print(f"bucket: {bucket}, Key: {output_key}")
        
        output_s3_uri = store_in_s3(bucket, output_key, error_output)
        
        return {
            'Success': False,
            'Error': f'Failed to download AWS Nuke binary: {str(e)}',
            'Output': error_output[:2000],
            'OutputS3Uri': output_s3_uri,
            'ResourcesToDelete': 0,
            'DryRun': dry_run,
            'SendNotification': send_notification
        }

    try:
        result = execute_nuke(nuke_binary, config_path, dry_run)
                
        print(f"Command completed with return code: {result.returncode}")
        print(f"Stdout length: {len(result.stdout) if result.stdout else 0}")
        print(f"Stderr length: {len(result.stderr) if result.stderr else 0}")
        
        full_output = result.stdout + result.stderr
        
        # Filter output based on mode
        if dry_run:
            # For dry-run, only show lines with "would remove"
            filtered_lines = [line for line in full_output.split('\n') if 'would remove' in line.lower()]
            filtered_output = '\n'.join(filtered_lines)
            resources_to_delete = len(filtered_lines)
        else:
            # For actual execution, show lines with "removed" or "would remove" (in case of errors)
            removed_lines = [line for line in full_output.split('\n') if 'removed' in line.lower()]
            would_remove_lines = [line for line in full_output.split('\n') if 'would remove' in line.lower()]
            filtered_lines = removed_lines + would_remove_lines
            filtered_output = '\n'.join(filtered_lines)
            resources_to_delete = len(removed_lines)  # Only count actually removed resources
        
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        output_key = f"nuke-outputs/nuke-output-{timestamp}-{'dryrun' if dry_run else 'execution'}.txt"

        output_s3_uri = store_in_s3(bucket, output_key, full_output)
        
        # Also upload filtered output
        filtered_output_key = f"nuke-outputs/nuke-filtered-{timestamp}-{'dryrun' if dry_run else 'execution'}.txt"

        body = filtered_output if filtered_output else 'No filtered output available'
        filtered_output_s3_uri = store_in_s3(bucket, filtered_output_key, body)
        
        response = {
            'Success': result.returncode == 0,
            'OutputS3Uri': output_s3_uri if not dry_run else filtered_output_s3_uri,  # Use full output for actual execution
            'ResourcesToDelete': resources_to_delete,
            'DryRun': dry_run,
            'Error': '' if result.returncode == 0 else f'AWS Nuke exited with code {result.returncode}',
            'SendNotification': send_notification
        }
        
        print(f"Returning response: {json.dumps(response, default=str)}")
        return response
        
    except subprocess.TimeoutExpired as e:
        # Upload timeout error to S3
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        
        # Get partial output from the exception
        partial_stdout = getattr(e, 'stdout', '') or ''
        partial_stderr = getattr(e, 'stderr', '') or ''
        partial_output = partial_stdout + partial_stderr
        
        error_output = f"AWS Nuke execution timed out after {e.timeout} seconds\n\n"
        if partial_output:
            error_output += f"Partial output:\n{partial_output}"
        else:
            error_output += "No partial output available"
        
        output_key = f"nuke-outputs/nuke-error-{timestamp}-timeout-{'dryrun' if dry_run else 'execution'}.txt"

        output_s3_uri = store_in_s3(bucket, output_key, error_output)
        
        response = {
            'Success': False,
            'Error': f'AWS Nuke execution timed out after {e.timeout} seconds',
            'OutputS3Uri': output_s3_uri,
            'ResourcesToDelete': 0,
            'DryRun': dry_run,
            'SendNotification': send_notification
        }
        
        print(f"Timeout - Returning response: {json.dumps(response, default=str)}")
        return response
    except Exception as e:
        # Upload general error to S3
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        error_output = f"AWS Nuke execution failed with error:\n{str(e)}\n\n"
        
        output_key = f"nuke-outputs/nuke-error-{timestamp}-exception-{'dryrun' if dry_run else 'execution'}.txt"
        
        output_s3_uri = store_in_s3(bucket, output_key, error_output)
        
        response = {
            'Success': False,
            'Error': str(e),
            'OutputS3Uri': output_s3_uri,
            'ResourcesToDelete': 0,
            'DryRun': dry_run,
            'SendNotification': send_notification
        }
        
        print(f"Exception - Returning response: {json.dumps(response, default=str)}")
        return response
