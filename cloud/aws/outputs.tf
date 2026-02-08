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

# IoT Core outputs (nullable when disabled)
output "iot_endpoint" {
  description = "AWS IoT Data endpoint address"
  value       = var.enable_iot ? data.aws_iot_endpoint.iot.endpoint_address : null
}

output "iot_thing_name" {
  description = "Name of the created IoT Thing for edge devices"
  value       = var.enable_iot ? aws_iot_thing.edge_thing[0].name : null
}

output "iot_certificate_pem" {
  description = "Device certificate PEM (sensitive)"
  value       = var.enable_iot ? tls_self_signed_cert.edge_cert[0].cert_pem : null
  sensitive   = true
}

output "iot_private_key" {
  description = "Device private key (sensitive)"
  value       = var.enable_iot ? tls_private_key.edge_key[0].private_key_pem : null
  sensitive   = true
}

# Labeling Module Outputs
output "labeling_instance_id" {
  description = "ID of the labeling EC2 instance"
  value       = var.enable_labeling ? module.labeling[0].instance_id : null
}

output "labeling_public_ip" {
  description = "Public IP of the labeling EC2 instance"
  value       = var.enable_labeling ? module.labeling[0].public_ip : null
}

output "labeling_bucket_name" {
  description = "Name of the labeling S3 bucket"
  value       = var.enable_labeling ? module.labeling[0].bucket_name : null
}

output "labeling_iam_role_arn" {
  description = "ARN of the labeling IAM role"
  value       = var.enable_labeling ? module.labeling[0].iam_role_arn : null
}
