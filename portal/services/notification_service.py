"""
Email and notification service using AWS SES and SNS
"""
from typing import Optional
from django.template.loader import render_to_string
from portal.services.vendors.aws_ses import AWSSESClient
from portal.services.vendors.aws_sns import AWSSNSClient


class NotificationService:
    """Email and notification service"""
    
    def __init__(self):
        self.ses_client = AWSSESClient()
        self.sns_client = AWSSNSClient()
    
    def send_email(
        self,
        to: str,
        subject: str,
        template_name: str,
        context: dict
    ) -> bool:
        """
        Send email using template
        
        Args:
            to: Recipient email
            subject: Email subject
            template_name: Template name (e.g., 'portal/emails/verification.html')
            context: Template context
        
        Returns:
            True if sent successfully
        """
        try:
            html_body = render_to_string(template_name, context)
            text_body = render_to_string(template_name.replace('.html', '.txt'), context) if template_name.endswith('.html') else None
            
            self.ses_client.send_email(to, subject, html_body, text_body)
            return True
        except Exception:
            return False
    
    def send_notification(
        self,
        user,
        channel: str,
        message: str
    ) -> bool:
        """
        Send notification via multiple channels
        
        Args:
            user: User instance
            channel: 'sms', 'email', 'push'
            message: Notification message
        
        Returns:
            True if sent successfully
        """
        try:
            if channel == 'sms' and hasattr(user, 'phone') and user.phone:
                self.sns_client.send_sms(user.phone, message)
                return True
            elif channel == 'email' and user.email:
                self.send_email(
                    user.email,
                    'Notification from Payswap',
                    'portal/emails/notification.html',
                    {'message': message, 'user': user}
                )
                return True
            return False
        except Exception:
            return False
