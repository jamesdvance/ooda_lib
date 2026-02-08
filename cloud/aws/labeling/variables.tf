variable "labeling_bucket_name" {
  description = "Name of the S3 bucket for labeled training data"
  type        = string
}

variable "labeling_iam_role_name" {
  description = "Name of the IAM role for the labeling EC2 instance"
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

variable "upload_bucket_arn" {
  description = "ARN of the upload S3 bucket (for reading raw video)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for the labeling server"
  type        = string
  default     = "t3.medium"
}

variable "auto_stop_idle_minutes" {
  description = "Minutes of low CPU before auto-stopping the instance (0 to disable)"
  type        = number
  default     = 30
}

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed to SSH into the labeling instance"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "aws_region" {
  description = "AWS region for resource creation"
  type        = string
}
