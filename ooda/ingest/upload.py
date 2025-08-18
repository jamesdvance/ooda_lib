import os 

def upload_to_s3(local_file, s3_client, bucket_name):
    """
    Upload file to S3 bucket
    """
    try:
        filename = os.path.basename(local_file)
        s3_key = f"video_chunks/{filename}"
        s3_client.upload_file(str(local_file), bucket_name, s3_key)
        print(f"Uploaded {filename} to s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"Failed to upload {filename}: {e}")