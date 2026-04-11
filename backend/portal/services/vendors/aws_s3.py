"""
AWS S3 storage client
"""
import boto3
from typing import Optional
from datetime import timedelta
from django.core.files.uploadedfile import UploadedFile
from core.config import payswap_config


class AWSS3Client:
    """AWS S3 storage client"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=payswap_config.S3_REGION,
            aws_access_key_id=payswap_config.get_s3_access_key(),
            aws_secret_access_key=payswap_config.get_s3_secret_key(),
            endpoint_url=payswap_config.S3_ENDPOINT_URL
        )
        self.bucket = payswap_config.S3_BUCKET
        self.region = payswap_config.S3_REGION
    
    def upload_file(self, file: UploadedFile, path: str) -> str:
        """
        Upload file to S3
        
        Args:
            file: Django uploaded file
            path: S3 path (e.g., 'kyc/user_123/document.pdf')
        
        Returns:
            S3 URL
        """
        try:
            self.s3_client.upload_fileobj(
                file,
                self.bucket,
                path,
                ExtraArgs={'ServerSideEncryption': 'AES256'}
            )
            url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{path}"
            return url
        except Exception as e:
            raise Exception(f"S3 upload error: {str(e)}")
    
    def get_signed_url(self, path: str, expiry_hours: int = 1) -> str:
        """
        Generate signed URL for private file access
        
        Args:
            path: S3 path
            expiry_hours: URL expiry in hours
        
        Returns:
            Signed URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': path},
                ExpiresIn=int(timedelta(hours=expiry_hours).total_seconds())
            )
            return url
        except Exception as e:
            raise Exception(f"S3 signed URL error: {str(e)}")
    
    def delete_file(self, path: str) -> bool:
        """
        Delete file from S3
        
        Args:
            path: S3 path
        
        Returns:
            True if deleted successfully
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False
