import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
from src.config.config import settings

def get_s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        region_name="auto",
    )

def upload_to_r2(file, filename: str, dataset_id: str) -> str:
    r2_path = f"datasets/{dataset_id}/{filename}"
    try:
        s3 = get_s3_client()
        s3.upload_fileobj(file, settings.R2_BUCKET_NAME, r2_path)
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"R2 upload failed: {str(e)}")
    return r2_path

def delete_from_r2(r2_path: str) -> None:
    try:
        s3 = get_s3_client()
        s3.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=r2_path)
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"R2 delete failed: {str(e)}")