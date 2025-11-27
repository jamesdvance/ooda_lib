variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "enable_upload" {
  description = "Enable the upload service (S3 bucket and IAM role for edge devices)"
  type        = bool
  default     = true
}

# Future module toggles:
# variable "enable_labeling" {
#   description = "Enable the labeling service (S3 bucket, EC2 instance, and IAM role)"
#   type        = bool
#   default     = false
# }
#
# variable "enable_training" {
#   description = "Enable the training service (EKS cluster and EFS volume)"
#   type        = bool
#   default     = false
# }
#
# variable "enable_release" {
#   description = "Enable the release service (EC2 instance for Jetson Nano emulator)"
#   type        = bool
#   default     = false
# }
#
# variable "enable_monitoring" {
#   description = "Enable the monitoring service (CloudWatch and Grafana)"
#   type        = bool
#   default     = false
# }
