#!/bin/bash
set -e

# Install Python 3.11 and pip
dnf install -y python3.11 python3.11-pip git

# Install FiftyOne
python3.11 -m pip install fiftyone

# Create working directory
mkdir -p /home/ec2-user/labeling
chown ec2-user:ec2-user /home/ec2-user/labeling

# Write helper script to start FiftyOne
cat > /home/ec2-user/labeling/start_fiftyone.sh << 'SCRIPT'
#!/bin/bash
# Sync raw video from upload bucket
aws s3 sync s3://${upload_bucket_name} /home/ec2-user/labeling/raw_video --region ${aws_region}

# Start FiftyOne App (accessible on port 5151)
python3.11 -c "
import fiftyone as fo
dataset = fo.Dataset('ooda-labeling')
dataset.persistent = True
session = fo.launch_app(dataset, address='0.0.0.0', port=5151)
session.wait()
"
SCRIPT
chmod +x /home/ec2-user/labeling/start_fiftyone.sh
chown ec2-user:ec2-user /home/ec2-user/labeling/start_fiftyone.sh

# Write helper script to export labels to S3
cat > /home/ec2-user/labeling/export_labels.sh << 'SCRIPT'
#!/bin/bash
# Export labeled dataset to S3
aws s3 sync /home/ec2-user/labeling/exports s3://${bucket_name}/labels --region ${aws_region}
echo "Labels exported to s3://${bucket_name}/labels"
SCRIPT
chmod +x /home/ec2-user/labeling/export_labels.sh
chown ec2-user:ec2-user /home/ec2-user/labeling/export_labels.sh
