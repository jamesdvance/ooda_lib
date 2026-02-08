// AWS IoT Core resources for edge device authentication

data "aws_iot_endpoint" "iot" {
  endpoint_type = "iot:Data-ATS"
}

# Generate private key for the IoT device
resource "tls_private_key" "edge_key" {
  count     = var.enable_iot ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

# Generate a self-signed certificate
resource "tls_self_signed_cert" "edge_cert" {
  count             = var.enable_iot ? 1 : 0
  private_key_pem   = tls_private_key.edge_key[0].private_key_pem
  subject {
    common_name = "ooda-edge-${data.aws_caller_identity.current.account_id}"
  }
  validity_period_hours = 8766 # ~1 year
  allowed_uses          = ["digital_signature"]
}

# Create IoT Thing
resource "aws_iot_thing" "edge_thing" {
  count = var.enable_iot ? 1 : 0
  name  = "ooda-edge-${data.aws_caller_identity.current.account_id}"
}

# Register certificate with AWS IoT
resource "aws_iot_certificate" "edge_cert" {
  count              = var.enable_iot ? 1 : 0
  certificate_pem    = tls_self_signed_cert.edge_cert[0].cert_pem
  active             = true
}

resource "aws_iot_policy" "edge_policy" {
  count = var.enable_iot ? 1 : 0

  name   = "ooda-edge-policy-${data.aws_caller_identity.current.account_id}"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["iot:Connect"]
        Resource = "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:client/${aws_iot_thing.edge_thing[0].name}"
      },
      {
        Effect = "Allow"
        Action = ["iot:Publish", "iot:Subscribe", "iot:Receive"]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topic/ooda/*",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current.account_id}:topicfilter/ooda/*"
        ]
      }
    ]
  })
}

resource "aws_iot_policy_attachment" "attach_policy" {
  count       = var.enable_iot ? 1 : 0
  policy = aws_iot_policy.edge_policy[0].name
  target      = aws_iot_certificate.edge_cert[0].arn
}

resource "aws_iot_thing_principal_attachment" "thing_attach" {
  count     = var.enable_iot ? 1 : 0
  thing = aws_iot_thing.edge_thing[0].name
  principal  = aws_iot_certificate.edge_cert[0].arn
}
