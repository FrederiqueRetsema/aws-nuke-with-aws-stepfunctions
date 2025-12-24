#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AwsNukeStack } from '../lib/aws-nuke-stack';

const app = new cdk.App();

// Get configuration from context or environment variables
const config = {
  projectName: app.node.tryGetContext('projectName') || process.env.PROJECT_NAME || 'aws-nuke',
  tagKey: app.node.tryGetContext('tagKey') || process.env.TAG_KEY || 'Cleanup',
  tagValue: app.node.tryGetContext('tagValue') || process.env.TAG_VALUE || 'persist',
  emailAddress: app.node.tryGetContext('emailAddress') || process.env.EMAIL_ADDRESS || '',
  allowedRegions: (() => {
    const contextRegions = app.node.tryGetContext('allowedRegions');
    if (Array.isArray(contextRegions)) return contextRegions;
    if (typeof contextRegions === 'string') return contextRegions.split(',');
    if (process.env.ALLOWED_REGIONS) return process.env.ALLOWED_REGIONS.split(',');
    return ['eu-west-1'];
  })(),
  blocklistAccounts: (() => {
    const contextAccounts = app.node.tryGetContext('blocklistAccounts');
    if (Array.isArray(contextAccounts)) return contextAccounts;
    if (typeof contextAccounts === 'string') return contextAccounts.split(',');
    if (process.env.BLOCKLIST_ACCOUNTS) return process.env.BLOCKLIST_ACCOUNTS.split(',');
    return ['1234567890'];
  })(),
  cdkBucketPrefix: app.node.tryGetContext('cdkBucketPrefix') || process.env.CDK_BUCKET_PREFIX || 'cdk-',
  scheduleExpression: app.node.tryGetContext('scheduleExpression') || process.env.SCHEDULE_EXPRESSION || 'manual',
  retentionDays: (() => {
    const contextRetention = app.node.tryGetContext('retentionDays');
    if (typeof contextRetention === 'number') return contextRetention;
    if (typeof contextRetention === 'string') return parseInt(contextRetention);
    if (process.env.RETENTION_DAYS) return parseInt(process.env.RETENTION_DAYS, 30);
    return 30;
  })(),
  nukeVersion: app.node.tryGetContext('nukeVersion') || process.env.NUKE_VERSION || 'v3.62.2',
  enforceVersion: (() => {
    const enforceVersion = app.node.tryGetContext('enforceVersion');
    if (typeof enforceVersion === 'boolean') return enforceVersion;
    if (typeof enforceVersion === 'string') return (enforceVersion.toLowerCase() == "true");
    if (process.env.ENFORCE_VERSION) return (process.env.ENFORCE_VERSION.toLowerCase() == "true");
    return false;
  })()
};

new AwsNukeStack(app, 'AwsNukeStack', {
  ...config,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'eu-west-1',
  },
  description: 'AWS Nuke - Safe resource cleanup with tag-based protection',
});

app.synth();