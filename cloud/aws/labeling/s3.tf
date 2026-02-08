# S3 Bucket for labeled training data
resource "aws_s3_bucket" "labeling_bucket" {
  bucket = var.labeling_bucket_name

  tags = {
    Name = "OODA Labeled Training Data"
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "labeling_bucket_pab" {
  bucket = aws_s3_bucket.labeling_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning
resource "aws_s3_bucket_versioning" "labeling_bucket_versioning" {
  bucket = aws_s3_bucket.labeling_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption configuration
resource "aws_s3_bucket_server_side_encryption_configuration" "labeling_bucket_encryption" {
  bucket = aws_s3_bucket.labeling_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Bucket policy to require HTTPS
resource "aws_s3_bucket_policy" "labeling_bucket_policy" {
  bucket = aws_s3_bucket.labeling_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureConnections"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.labeling_bucket.arn,
          "${aws_s3_bucket.labeling_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
