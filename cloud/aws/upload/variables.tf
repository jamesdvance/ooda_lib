variable "upload_bucket_name" {
  description = "Name of the S3 bucket for raw video uploads"
  type        = string
}

variable "upload_iam_role_name" {
  description = "Name of the IAM role for edge device uploads"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the shared KMS key for S3 encryption"
  type        = string
}

variable "kms_key_id" {
  description = "ID of the shared KMS key for S3 encryption"
  type        = string
}