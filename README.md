# OODA Lib

Manage your full training, deploying, and measuring lifecyle for homebrew computer vision projects on Nvidia Jetson nano. 
Low cost is a top concern across all solution choices. To achieve this, we share compute when available and avoid platform as a service. 


## Domains
See [cloud readme](./cloud/aws/ReadMe.md) for description of all infrastructure deployed

### Persisting
* Save video data to the cloud in a cost-optimized way

### Labeling
* Implement your favorite labeling software (Voxel51, CVAT) on a low-cost ec2 instance. Only pay while using

### Training & Experimentation
* Train using Kubeflow train, preconfigured to access your labeled training data

### Model Testing
* Publish artifact to low-cost ec2 instance with jetson nano emulator and run test suite

### Deployment
* Automatically deploy the optimized and tested artifact to your Jetson

![System Diagram](./assets/OODA_Lib.drawio.png)

## Ethos 

### Cost Efficiency
Homebrew users (and their spouses!) demand the lowest cost possible 

### Modularity
Maybe you don't want the cost of a step to emulate the model before releasing it to production. Cloud infrastructure is arranged by domain to make it easy to avoid or remove what isn't needed. 

### Simplicity
It's not just lip service. We want the fewest keystrokes possible in order to deploy and test our camera system.

## Getting Started

### 1. Deploy Cloud Infrastructure

From the `cloud/aws` directory:

```bash
terraform init
terraform apply
```

This provisions S3 buckets, KMS keys, IAM roles, and IoT resources. After apply, Terraform generates edge device configuration files automatically:

- `ooda/edge/upload/.env.generated` — S3 bucket name, region, IoT endpoint, and upload settings
- `ooda/edge/certs/iot_certificate.pem` — IoT device certificate
- `ooda/edge/certs/iot_private_key.pem` — IoT device private key

### 2. Configure the Edge Device

On the edge device (or before copying files over), run the configure script with your AWS credentials:

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
cd ooda/edge
./configure.sh
```

This copies the Terraform-generated config into `upload/.env` and injects your AWS credentials.

### 3. Copy to Edge Device

Copy the `ooda/edge` directory to your Jetson Nano, then run:

```bash
./install.sh
./run.sh
```

## Future Work
* AgentOps workflows for actions taken on video
* Auto-labeling for self-supervised learning