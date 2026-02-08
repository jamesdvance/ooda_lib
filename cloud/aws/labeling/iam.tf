# IAM Role for the labeling EC2 instance
resource "aws_iam_role" "labeling_role" {
  name = var.labeling_iam_role_name

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
    Name = "OODA Labeling Role"
  }
}

# S3 read/write policy for the labeling bucket
resource "aws_iam_policy" "labeling_s3_policy" {
  name = "${var.labeling_iam_role_name}-s3-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadUploadBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.upload_bucket_arn,
          "${var.upload_bucket_arn}/*"
        ]
      },
      {
        Sid    = "ReadWriteLabelingBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.labeling_bucket.arn,
          "${aws_s3_bucket.labeling_bucket.arn}/*"
        ]
      }
    ]
  })
}

# KMS policy for decrypting/encrypting S3 objects
resource "aws_iam_policy" "labeling_kms_policy" {
  name = "${var.labeling_iam_role_name}-kms-policy"

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
resource "aws_iam_role_policy_attachment" "labeling_s3_attachment" {
  role       = aws_iam_role.labeling_role.name
  policy_arn = aws_iam_policy.labeling_s3_policy.arn
}

resource "aws_iam_role_policy_attachment" "labeling_kms_attachment" {
  role       = aws_iam_role.labeling_role.name
  policy_arn = aws_iam_policy.labeling_kms_policy.arn
}

# Instance profile for EC2
resource "aws_iam_instance_profile" "labeling_instance_profile" {
  name = "${var.labeling_iam_role_name}-instance-profile"
  role = aws_iam_role.labeling_role.name
}
