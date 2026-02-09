"""
Leegality API client for Document Signing and Stamp Paper
Based on Leegality API v3 documentation: https://docs.leegality.com/v3
"""
import httpx
import hashlib
import hmac
import base64
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from core.config import payswap_config


class LeegalityClient:
    """Leegality API client for document signing and stamp paper management"""
    
    def __init__(self, auth_token: Optional[str] = None, private_salt: Optional[str] = None):
        """
        Initialize Leegality client
        
        Args:
            auth_token: Leegality AuthToken
            private_salt: Leegality PrivateSalt
        """
        # Get credentials from config or parameters
        config_token = getattr(payswap_config, 'LEGALITY_AUTH_TOKEN', None)
        config_salt = getattr(payswap_config, 'LEGALITY_PRIVATE_SALT', None)
        
        # Handle SecretStr type from config
        if config_token:
            self.auth_token = auth_token or (config_token.get_secret_value() if hasattr(config_token, 'get_secret_value') else str(config_token))
        else:
            self.auth_token = auth_token
        
        if config_salt:
            self.private_salt = private_salt or (config_salt.get_secret_value() if hasattr(config_salt, 'get_secret_value') else str(config_salt))
        else:
            self.private_salt = private_salt
        
        # Leegality API base URL
        self.base_url = "https://api.leegality.com/v3"
        
        if not self.auth_token or not self.private_salt:
            raise ValueError("Leegality AuthToken and PrivateSalt are required")
    
    def _generate_signature(self, method: str, endpoint: str, body: Optional[Dict] = None, timestamp: Optional[str] = None) -> str:
        """
        Generate signature for Leegality API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            body: Request body as dict
            timestamp: Request timestamp (ISO format)
        
        Returns:
            Base64 encoded signature
        """
        if not timestamp:
            timestamp = datetime.utcnow().isoformat() + 'Z'
        
        # Create message to sign
        message_parts = [method.upper(), endpoint]
        if body:
            message_parts.append(json.dumps(body, sort_keys=True, separators=(',', ':')))
        message_parts.append(timestamp)
        message = '\n'.join(message_parts)
        
        # Generate HMAC signature
        signature = hmac.new(
            self.private_salt.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Return base64 encoded signature
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_headers(self, method: str, endpoint: str, body: Optional[Dict] = None) -> Dict[str, str]:
        """
        Get headers for Leegality API request
        
        Args:
            method: HTTP method
            endpoint: API endpoint path
            body: Request body
        
        Returns:
            Headers dict
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        signature = self._generate_signature(method, endpoint, body, timestamp)
        
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "X-Leegality-Signature": signature,
            "X-Leegality-Timestamp": timestamp,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def create_document(
        self,
        file: str,
        name: str,
        invitations: List[Dict],
        workflow_id: Optional[str] = None,
        template_id: Optional[str] = None,
        custom_message: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Create a document for signing
        
        Args:
            file: Base64 encoded file content or file URL
            name: Document name
            invitations: List of invitation objects with signer details
            workflow_id: Optional workflow ID
            template_id: Optional template ID
            custom_message: Custom message for signers
            **kwargs: Additional parameters
        
        Returns:
            API response dict
        """
        url = f"{self.base_url}/documents"
        
        data = {
            "file": file,
            "name": name,
            "invitations": invitations
        }
        
        if workflow_id:
            data["workflow"] = {"id": workflow_id}
        
        if template_id:
            data["template"] = {"id": template_id}
        
        if custom_message:
            data["customMessage"] = custom_message
        
        # Add any additional parameters
        data.update(kwargs)
        
        headers = self._get_headers("POST", "/documents", data)
        
        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            raise Exception(f"Leegality API error: {error_detail}")
        except Exception as e:
            raise Exception(f"Leegality API error: {str(e)}")
    
    def get_document_status(self, document_id: str) -> Dict:
        """
        Get document status
        
        Args:
            document_id: Document ID
        
        Returns:
            Document status response
        """
        url = f"{self.base_url}/documents/{document_id}"
        headers = self._get_headers("GET", f"/documents/{document_id}")
        
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            raise Exception(f"Leegality API error: {error_detail}")
        except Exception as e:
            raise Exception(f"Leegality API error: {str(e)}")
    
    def create_stamp_paper(
        self,
        document_id: str,
        stamp_details: Dict,
        **kwargs
    ) -> Dict:
        """
        Create stamp paper for document
        
        Args:
            document_id: Document ID
            stamp_details: Stamp details including:
                - groupName: Stamp group name
                - groupNumber: Stamp group number
                - stampValue: Stamp value
                - state: State for stamp
                - firstParty: First party name
                - secondParty: Second party name
                - stampDutyAmount: Stamp duty amount
                - considerationPrice: Consideration price
                - descriptionOfDocument: Document description
                - stampDutyPaidBy: Who pays stamp duty
                - articleCode: Article code
            **kwargs: Additional parameters
        
        Returns:
            API response dict
        """
        url = f"{self.base_url}/documents/{document_id}/stamps"
        
        data = {
            "stampDetails": stamp_details
        }
        data.update(kwargs)
        
        headers = self._get_headers("POST", f"/documents/{document_id}/stamps", data)
        
        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            raise Exception(f"Leegality API error: {error_detail}")
        except Exception as e:
            raise Exception(f"Leegality API error: {str(e)}")
    
    def get_stamp_status(self, document_id: str) -> Dict:
        """
        Get stamp paper status for document
        
        Args:
            document_id: Document ID
        
        Returns:
            Stamp status response
        """
        url = f"{self.base_url}/documents/{document_id}/stamps"
        headers = self._get_headers("GET", f"/documents/{document_id}/stamps")
        
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            raise Exception(f"Leegality API error: {error_detail}")
        except Exception as e:
            raise Exception(f"Leegality API error: {str(e)}")
    
    def download_document(self, document_id: str) -> bytes:
        """
        Download signed document
        
        Args:
            document_id: Document ID
        
        Returns:
            Document file bytes
        """
        url = f"{self.base_url}/documents/{document_id}/download"
        headers = self._get_headers("GET", f"/documents/{document_id}/download")
        
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            raise Exception(f"Leegality API error: {error_detail}")
        except Exception as e:
            raise Exception(f"Leegality API error: {str(e)}")
    
    def get_audit_trail(self, document_id: str) -> Dict:
        """
        Get document audit trail
        
        Args:
            document_id: Document ID
        
        Returns:
            Audit trail response
        """
        url = f"{self.base_url}/documents/{document_id}/audit-trail"
        headers = self._get_headers("GET", f"/documents/{document_id}/audit-trail")
        
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_response = e.response.json()
                error_detail = error_response.get('message', str(e))
            except:
                error_detail = str(e)
            raise Exception(f"Leegality API error: {error_detail}")
        except Exception as e:
            raise Exception(f"Leegality API error: {str(e)}")
