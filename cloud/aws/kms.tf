# KMS Key for S3 bucket encryption across all modules
resource "aws_kms_key" "s3_encryption_key" {
  description             = "KMS key for S3 bucket encryption (shared across modules)"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 Service"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "OODA S3 Encryption Key"
  }
}

resource "aws_kms_alias" "s3_encryption_key_alias" {
  name          = "alias/ooda-encryption-key"
  target_key_id = aws_kms_key.s3_encryption_key.key_id
}
