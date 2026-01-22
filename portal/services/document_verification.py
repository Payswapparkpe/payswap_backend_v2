"""
Document verification service with vendor abstraction
"""
from typing import Dict, Optional
from enum import Enum
from portal.services.vendors.cashfree import CashfreeClient
from portal.services.vendors.invincible_ocean import InvincibleOceanClient


class VerificationVendor(str, Enum):
    """Verification vendor options"""
    CASHFREE = "cashfree"
    INVINCIBLE_OCEAN = "invincible_ocean"


class DocumentVerificationService:
    """Document verification service with vendor abstraction"""
    
    def __init__(self, preferred_vendor: VerificationVendor = VerificationVendor.CASHFREE):
        self.preferred_vendor = preferred_vendor
        self.cashfree_client = CashfreeClient()
        self.invincible_ocean_client = InvincibleOceanClient()
    
    def verify(
        self,
        document_type: str,
        document_number: str,
        file_path: str,
        vendor: Optional[VerificationVendor] = None
    ) -> Dict:
        """
        Verify document using specified or preferred vendor
        
        Args:
            document_type: Document type (aadhaar, pan, etc.)
            document_number: Document number
            file_path: Path to document file
            vendor: Vendor to use (optional, uses preferred if not specified)
        
        Returns:
            Standardized verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_document(document_type, document_number, file_path)
            elif vendor == VerificationVendor.INVINCIBLE_OCEAN:
                response = self.invincible_ocean_client.verify_document(document_type, document_number, file_path)
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            # Standardize response
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            # Try failover to other vendor
            if vendor == VerificationVendor.CASHFREE:
                try:
                    response = self.invincible_ocean_client.verify_document(document_type, document_number, file_path)
                    return self._standardize_response(response, VerificationVendor.INVINCIBLE_OCEAN)
                except Exception:
                    raise e
            else:
                try:
                    response = self.cashfree_client.verify_document(document_type, document_number, file_path)
                    return self._standardize_response(response, VerificationVendor.CASHFREE)
                except Exception:
                    raise e
    
    def _standardize_response(self, response: Dict, vendor: VerificationVendor) -> Dict:
        """
        Standardize vendor response to common format
        
        Args:
            response: Vendor-specific response
            vendor: Vendor used
        
        Returns:
            Standardized response dict
        """
        # Standardize to common format
        # Format: {'status': 'success'|'failed', 'verified': bool, 'details': dict}
        standardized = {
            'vendor': vendor.value,
            'raw_response': response,
        }
        
        # Extract common fields (implementation depends on actual API responses)
        if vendor == VerificationVendor.CASHFREE:
            standardized['status'] = response.get('status', 'unknown')
            standardized['verified'] = response.get('status') == 'success'
        elif vendor == VerificationVendor.INVINCIBLE_OCEAN:
            standardized['status'] = response.get('verification_status', 'unknown')
            standardized['verified'] = response.get('verified', False)
        
        return standardized
