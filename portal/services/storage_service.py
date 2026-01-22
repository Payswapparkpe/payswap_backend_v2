"""
File storage service using AWS S3
"""
from typing import List, Optional
from django.core.files.uploadedfile import UploadedFile
from portal.services.vendors.aws_s3 import AWSS3Client


class StorageService:
    """File storage service"""
    
    def __init__(self):
        self.s3_client = AWSS3Client()
    
    def upload_kyc_document(self, user_id: int, document_type: str, file: UploadedFile) -> str:
        """
        Upload KYC document to S3
        
        Args:
            user_id: User ID
            document_type: Document type
            file: Uploaded file
        
        Returns:
            S3 URL
        """
        # Generate path: kyc/{user_id}/{document_type}/{filename}
        filename = file.name
        path = f"kyc/{user_id}/{document_type}/{filename}"
        return self.s3_client.upload_file(file, path)
    
    def upload_profile_image(self, profile_id: int, file: UploadedFile) -> str:
        """
        Upload profile image to S3
        
        Args:
            profile_id: Profile ID
            file: Uploaded file
        
        Returns:
            S3 URL
        """
        filename = file.name
        path = f"profiles/{profile_id}/{filename}"
        return self.s3_client.upload_file(file, path)
    
    def get_signed_url(self, s3_url: str, expiry_hours: int = 1) -> Optional[str]:
        """
        Get signed URL for S3 file
        
        Args:
            s3_url: Full S3 URL
            expiry_hours: Expiry in hours
        
        Returns:
            Signed URL or None
        """
        # Extract path from URL
        # Format: https://bucket.s3.region.amazonaws.com/path
        try:
            path = s3_url.split('.amazonaws.com/')[-1]
            return self.s3_client.get_signed_url(path, expiry_hours)
        except Exception:
            return None
    
    def delete_file(self, s3_url: str) -> bool:
        """
        Delete file from S3
        
        Args:
            s3_url: Full S3 URL
        
        Returns:
            True if deleted
        """
        try:
            path = s3_url.split('.amazonaws.com/')[-1]
            return self.s3_client.delete_file(path)
        except Exception:
            return False
