terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Data source to get current AWS account ID
data "aws_caller_identity" "current" {}

# Upload Module - Conditionally deployed based on enable_upload variable
module "upload" {
  count  = var.enable_upload ? 1 : 0
  source = "./upload"

  upload_bucket_name   = "ooda-raw-video-${data.aws_caller_identity.current.account_id}"
  upload_iam_role_name = "ooda-edge-role-${data.aws_caller_identity.current.account_id}"
  kms_key_arn          = aws_kms_key.s3_encryption_key.arn
  kms_key_id           = aws_kms_key.s3_encryption_key.key_id
}

# Labeling Module - Conditionally deployed based on enable_labeling variable
module "labeling" {
  count  = var.enable_labeling ? 1 : 0
  source = "./labeling"

  labeling_bucket_name   = "ooda-processed-video-${data.aws_caller_identity.current.account_id}"
  labeling_iam_role_name = "ooda-labeling-role-${data.aws_caller_identity.current.account_id}"
  upload_bucket_arn      = var.enable_upload ? module.upload[0].bucket_arn : ""
  kms_key_arn            = aws_kms_key.s3_encryption_key.arn
  kms_key_id             = aws_kms_key.s3_encryption_key.key_id
  aws_region             = var.aws_region
}
