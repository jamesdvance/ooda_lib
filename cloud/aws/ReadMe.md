# Cloud Via AWS

## To Deploy
First, install [terraform CLI](https://developer.hashicorp.com/terraform/cli/commands) and create default AWS authentication. 

#### 1. Deploy to Account 
`terraform init && terraform apply`

#### 2. Remove assets
`terraform destroy` 
*Note* -  AWS S3 Buckets with contents must be emptied and deleted manually from the console

## Design

![System Diagram](../../assets/OODA_Lib.drawio.png)

## Services & Assets

### Upload Service
Uploads video files from edge device into an S3 bucket. 

#### Assets
* S3 bucket - holds raw processed video
* Iam Role - allows write access to s3 from edge device

### Labeling Service
Provides a low-cost EC2 instance running [Voxel51 FiftyOne](https://docs.voxel51.com/) for dataset exploration and annotation. The instance auto-stops after 30 minutes of idle CPU to minimize costs (~$0.04/hr when running).

#### Enable
Set `enable_labeling = true` in your Terraform variables and run `terraform apply`.

#### Usage
1. SSH into the instance:
   ```bash
   ssh ec2-user@$(terraform output -raw labeling_public_ip)
   ```
2. Start FiftyOne (syncs raw video from the upload bucket and launches the UI):
   ```bash
   ./labeling/start_fiftyone.sh
   ```
3. Open the FiftyOne UI in your browser at `http://<public_ip>:5151`
4. When done labeling, export labels to S3:
   ```bash
   ./labeling/export_labels.sh
   ```
5. The instance will auto-stop after 30 minutes of inactivity. To start it again:
   ```bash
   aws ec2 start-instances --instance-ids $(terraform output -raw labeling_instance_id)
   ```

#### Assets
* S3 bucket (`ooda-processed-video-<acct_id>`) - holds labeled training data
* EC2 instance (t3.medium) - runs FiftyOne labeling software
* IAM role - read access to upload bucket, read/write to labeling bucket
* CloudWatch alarm - auto-stops instance when idle

### Training Service
* EKS Cluster - training and experimentation notebooks
* EFS Volume - holds training data

#### Release Service
* EC2 instance - EC2 instance with Jetson Nano emulator to test model before production



## Organization

The terraform assets are organized by domain, to allow users to easily deploy the capabilities they need, and refrain from what they don't. Below is the folder organization:

```
aws/
|--upload/ 
    |--s3.tf
        |--ooda-raw-video-<acct_id>
    |--iam.tf
        |--ooda_edge_role-<acct_id>

|--labeling/
    |--s3.tf
        |--ooda-processed-video-<acct_id>
    |--ec2.tf 
        |--ooda_labeling
    |--iam.tf
        |--ooda_labeling_role
    |--startup_script.sh

|--training/
    |--eks.tf
        |--ooda_kubeflow
    |--efs.tf
        |--ooda_fs
    |--kubeflow_install.sh

|--release/
    |--ec2.tf
        |--ooda_jetson_sim
    |--iam.tf

|--monitoring/
    |--cloudwatch.tf
        |--ooda_upload_service_down_alarm
    |--grafana.tf
        |--ooda_managed_grafana
     
```