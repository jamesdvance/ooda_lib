output "instance_id" {
  description = "ID of the labeling EC2 instance"
  value       = aws_instance.labeling.id
}

output "public_ip" {
  description = "Public IP of the labeling EC2 instance"
  value       = aws_instance.labeling.public_ip
}

output "bucket_name" {
  description = "Name of the labeling S3 bucket"
  value       = aws_s3_bucket.labeling_bucket.id
}

output "bucket_arn" {
  description = "ARN of the labeling S3 bucket"
  value       = aws_s3_bucket.labeling_bucket.arn
}

output "iam_role_name" {
  description = "Name of the labeling IAM role"
  value       = aws_iam_role.labeling_role.name
}

output "iam_role_arn" {
  description = "ARN of the labeling IAM role"
  value       = aws_iam_role.labeling_role.arn
}

output "security_group_id" {
  description = "ID of the labeling security group"
  value       = aws_security_group.labeling_sg.id
}
