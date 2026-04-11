"""
AWS SES email client
"""
import boto3
from typing import Optional
from django.conf import settings
from core.config import payswap_config


class AWSSESClient:
    """AWS SES email client"""
    
    def __init__(self):
        self.region = payswap_config.S3_REGION
        self.client = boto3.client(
            'ses',
            region_name=self.region,
            aws_access_key_id=payswap_config.get_s3_access_key(),
            aws_secret_access_key=payswap_config.get_s3_secret_key()
        )
        self.from_email = payswap_config.SMTP_DEFAULT_FROM
    
    def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> dict:
        """
        Send email via AWS SES
        
        Args:
            to: Recipient email
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text body (optional)
        
        Returns:
            API response dict
        """
        destination = {'ToAddresses': [to]}
        message = {
            'Subject': {'Data': subject, 'Charset': 'UTF-8'},
            'Body': {
                'Html': {'Data': html_body, 'Charset': 'UTF-8'}
            }
        }
        
        if text_body:
            message['Body']['Text'] = {'Data': text_body, 'Charset': 'UTF-8'}
        
        try:
            response = self.client.send_email(
                Source=self.from_email,
                Destination=destination,
                Message=message
            )
            return response
        except Exception as e:
            raise Exception(f"AWS SES error: {str(e)}")
