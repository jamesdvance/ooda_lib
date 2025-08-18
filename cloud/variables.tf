variable "bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
}

variable "iam_role_name" {
  description = "Name of the IAM role"
  type        = string
  default     = "s3-kms-access-role"
}