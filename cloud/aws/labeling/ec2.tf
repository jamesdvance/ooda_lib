# Get latest Amazon Linux 2023 AMI
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Get default VPC
data "aws_vpc" "default" {
  default = true
}

# Security group for labeling instance
resource "aws_security_group" "labeling_sg" {
  name        = "ooda-labeling-sg"
  description = "Security group for OODA labeling instance"
  vpc_id      = data.aws_vpc.default.id

  # SSH access
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.allowed_ssh_cidrs
  }

  # FiftyOne web UI
  ingress {
    description = "FiftyOne UI"
    from_port   = 5151
    to_port     = 5151
    protocol    = "tcp"
    cidr_blocks = var.allowed_ssh_cidrs
  }

  # Outbound access
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ooda-labeling-sg"
  }
}

# Labeling EC2 instance
resource "aws_instance" "labeling" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.labeling_instance_profile.name
  vpc_security_group_ids = [aws_security_group.labeling_sg.id]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
    kms_key_id  = var.kms_key_arn
  }

  user_data = base64encode(templatefile("${path.module}/startup_script.sh", {
    bucket_name        = var.labeling_bucket_name
    upload_bucket_name = split(":", var.upload_bucket_arn)[5]
    aws_region         = var.aws_region
  }))

  tags = {
    Name = "ooda-labeling"
  }
}

# Auto-stop after idle period using CloudWatch alarm
resource "aws_cloudwatch_metric_alarm" "labeling_idle_stop" {
  count = var.auto_stop_idle_minutes > 0 ? 1 : 0

  alarm_name          = "ooda-labeling-idle-stop"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = var.auto_stop_idle_minutes / 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 5
  alarm_description   = "Stop labeling instance when idle for ${var.auto_stop_idle_minutes} minutes"

  dimensions = {
    InstanceId = aws_instance.labeling.id
  }

  alarm_actions = ["arn:aws:automate:${var.aws_region}:ec2:stop"]
}
