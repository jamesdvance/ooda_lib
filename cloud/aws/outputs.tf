# Shared KMS Key Outputs
output "kms_key_id" {
  description = "ID of the shared KMS key for S3 encryption"
  value       = aws_kms_key.s3_encryption_key.key_id
}

output "kms_key_arn" {
  description = "ARN of the shared KMS key for S3 encryption"
  value       = aws_kms_key.s3_encryption_key.arn
}

# Upload Module Outputs
output "upload_bucket_name" {
  description = "Name of the upload S3 bucket"
  value       = var.enable_upload ? module.upload[0].bucket_name : null
}

output "upload_bucket_arn" {
  description = "ARN of the upload S3 bucket"
  value       = var.enable_upload ? module.upload[0].bucket_arn : null
}

output "upload_iam_role_name" {
  description = "Name of the upload IAM role"
  value       = var.enable_upload ? module.upload[0].iam_role_name : null
}

output "upload_iam_role_arn" {
  description = "ARN of the upload IAM role"
  value       = var.enable_upload ? module.upload[0].iam_role_arn : null
}

output "upload_instance_profile_name" {
  description = "Name of the upload instance profile"
  value       = var.enable_upload ? module.upload[0].instance_profile_name : null
}
