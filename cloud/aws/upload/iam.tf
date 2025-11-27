# IAM Role with S3 write and KMS permissions
resource "aws_iam_role" "s3_kms_role" {
  name = var.upload_iam_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "S3 KMS Access Role"
  }
}

# IAM Policy for S3 write permissions
resource "aws_iam_policy" "s3_write_policy" {
  name = "${var.upload_iam_role_name}-s3-write-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.secure_bucket.arn,
          "${aws_s3_bucket.secure_bucket.arn}/*"
        ]
      }
    ]
  })
}

# IAM Policy for KMS permissions
resource "aws_iam_policy" "kms_policy" {
  name = "${var.upload_iam_role_name}-kms-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# Attach policies to the IAM role
resource "aws_iam_role_policy_attachment" "s3_write_attachment" {
  role       = aws_iam_role.s3_kms_role.name
  policy_arn = aws_iam_policy.s3_write_policy.arn
}

resource "aws_iam_role_policy_attachment" "kms_attachment" {
  role       = aws_iam_role.s3_kms_role.name
  policy_arn = aws_iam_policy.kms_policy.arn
}

# Instance profile for EC2 instances to use this role
resource "aws_iam_instance_profile" "s3_kms_instance_profile" {
  name = "${var.upload_iam_role_name}-instance-profile"
  role = aws_iam_role.s3_kms_role.name
}
