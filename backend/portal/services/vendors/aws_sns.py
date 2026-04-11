"""
AWS SNS notification client
"""
import boto3
from typing import Optional
from core.config import payswap_config


class AWSSNSClient:
    """AWS SNS notification client"""
    
    def __init__(self):
        self.region = payswap_config.S3_REGION
        self.client = boto3.client(
            'sns',
            region_name=self.region,
            aws_access_key_id=payswap_config.get_s3_access_key(),
            aws_secret_access_key=payswap_config.get_s3_secret_key()
        )
    
    def send_sms(self, phone_number: str, message: str) -> dict:
        """
        Send SMS via AWS SNS
        
        Args:
            phone_number: Phone number with country code
            message: SMS message
        
        Returns:
            API response dict
        """
        try:
            response = self.client.publish(
                PhoneNumber=phone_number,
                Message=message
            )
            return response
        except Exception as e:
            raise Exception(f"AWS SNS error: {str(e)}")
    
    def send_push_notification(self, endpoint_arn: str, message: str) -> dict:
        """
        Send push notification
        
        Args:
            endpoint_arn: SNS endpoint ARN
            message: Notification message
        
        Returns:
            API response dict
        """
        try:
            response = self.client.publish(
                TargetArn=endpoint_arn,
                Message=message,
                MessageStructure='json'
            )
            return response
        except Exception as e:
            raise Exception(f"AWS SNS push error: {str(e)}")
