# Cloud Via AWS

## To Deploy
First, install [terraform CLI](https://developer.hashicorp.com/terraform/cli/commands) and create default AWS authentication. 

#### 1. Deploy to Account 
`terraform init && terraform apply`

#### 2. Remove assets
`terraform destroy` 
*Note* -  AWS S3 Buckets with contents must be emptied and deleted manually from the console
