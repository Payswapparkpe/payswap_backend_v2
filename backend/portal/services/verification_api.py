"""
Verification API service with support for multiple vendors
Supports Cashfree and other verification vendors
"""
from typing import Dict, Optional, List
from enum import Enum
from portal.services.vendors.cashfree import CashfreeClient


class VerificationVendor(str, Enum):
    """Verification vendor options"""
    CASHFREE = "cashfree"
    # Add more vendors as needed
    # VENDOR_2 = "vendor_2"


class VerificationAPIService:
    """Verification API service with multi-vendor support"""
    
    def __init__(self, preferred_vendor: VerificationVendor = VerificationVendor.CASHFREE):
        """
        Initialize Verification API service
        
        Args:
            preferred_vendor: Preferred vendor to use (default: Cashfree)
        """
        self.preferred_vendor = preferred_vendor
        self.cashfree_client = CashfreeClient()
        # Initialize other vendor clients as needed
        # self.vendor_2_client = Vendor2Client()
    
    def verify_document(
        self,
        document_type: str,
        document_number: str,
        file_path: Optional[str] = None,
        vendor: Optional[VerificationVendor] = None
    ) -> Dict:
        """
        Verify document using specified or preferred vendor
        
        Args:
            document_type: Document type (aadhaar, pan, driving_license, etc.)
            document_number: Document number
            file_path: Optional path to document file
            vendor: Vendor to use (optional, uses preferred if not specified)
        
        Returns:
            Standardized verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_document(
                    document_type=document_type,
                    document_number=document_number,
                    file_path=file_path
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            # Standardize response
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            # Try failover to other vendor if available
            if vendor == VerificationVendor.CASHFREE:
                # Add failover logic here if other vendors are available
                raise e
            else:
                # Try Cashfree as fallback
                try:
                    response = self.cashfree_client.verify_document(
                        document_type=document_type,
                        document_number=document_number,
                        file_path=file_path
                    )
                    return self._standardize_response(response, VerificationVendor.CASHFREE)
                except Exception:
                    raise e
    
    def verify_pan(self, pan_number: str, name: Optional[str] = None, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify PAN card
        
        Args:
            pan_number: PAN card number
            name: Optional name to verify
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
            **kwargs: Logging parameters (user_id, request_id, client_ip, user_agent)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_pan(
                    pan_number=pan_number,
                    name=name,
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_aadhaar(self, aadhaar_number: str, name: Optional[str] = None, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify Aadhaar card
        
        Args:
            aadhaar_number: Aadhaar number
            name: Optional name to verify
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
            **kwargs: Logging parameters (user_id, request_id, client_ip, user_agent)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_aadhaar(
                    aadhaar_number=aadhaar_number,
                    name=name,
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_bank_account(
        self,
        account_number: str,
        ifsc_code: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        vendor: Optional[VerificationVendor] = None,
        **kwargs
    ) -> Dict:
        """
        Verify bank account details
        
        Args:
            account_number: Bank account number
            ifsc_code: IFSC code
            name: Optional account holder name
            phone: Optional phone number
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_bank_account(
                    account_number=account_number,
                    ifsc_code=ifsc_code,
                    name=name,
                    phone=phone,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_phone(self, phone_number: str, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify phone number
        
        Args:
            phone_number: Phone number to verify
            vendor: Vendor to use (optional)
            **kwargs: Logging parameters (user_id, request_id, client_ip, user_agent)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                # Implement phone verification via Cashfree
                response = self.cashfree_client.verify_phone(
                    phone_number=phone_number,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_email(self, email: str, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify email address
        
        Args:
            email: Email address to verify
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_email(
                    email=email,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_driving_license(self, dl_number: str, dob: Optional[str] = None, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify Driving License
        
        Args:
            dl_number: Driving License number
            dob: Date of birth (YYYY-MM-DD) - REQUIRED
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_driving_license(
                    dl_number=dl_number, 
                    dob=dob,
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_voter_id(self, voter_id: str, name: Optional[str] = None, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify Voter ID (EPIC number)
        
        Args:
            voter_id: EPIC number (Electoral Photo Identity Card number)
            name: Optional name to verify
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_voter_id(
                    voter_id=voter_id, 
                    name=name,
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_passport(self, passport_number: str, dob: Optional[str] = None, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify Passport (using file_number)
        
        Args:
            passport_number: Passport file number (not passport number)
            dob: Date of birth (YYYY-MM-DD) - REQUIRED
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_passport(
                    passport_number=passport_number, 
                    dob=dob,
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_gst(self, gstin: str, business_name: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify GSTIN
        
        Args:
            gstin: GST Identification Number
            business_name: Optional business name to verify
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_gst(
                    gstin=gstin, 
                    business_name=business_name,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_cin(self, cin: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify CIN (Corporate Identification Number)
        
        Args:
            cin: CIN number
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_cin(
                    cin=cin, 
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_ifsc(self, ifsc_code: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify IFSC code
        
        Args:
            ifsc_code: IFSC code (11 characters)
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_ifsc(
                    ifsc_code=ifsc_code, 
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_vehicle_rc(self, vehicle_number: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Verify Vehicle Registration Certificate
        
        Args:
            vehicle_number: Vehicle registration number
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_vehicle_rc(
                    vehicle_number=vehicle_number, 
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_face_liveness(self, image_base64: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Face Liveness Check - Detect live human presence
        
        Args:
            image_base64: Base64 encoded face image
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_face_liveness(
                    image_base64=image_base64, 
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_face_match(self, image1_base64: str, image2_base64: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Face Match - Compare facial features between two images
        
        Args:
            image1_base64: Base64 encoded first image
            image2_base64: Base64 encoded second image
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_face_match(
                    image1_base64=image1_base64,
                    image2_base64=image2_base64,
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def verify_name_match(self, name1: str, name2: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Name Match - Verify names with variations and fuzzy matching
        
        Args:
            name1: First name to compare
            name2: Second name to compare
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.verify_name_match(
                    name1=name1,
                    name2=name2,
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    def smart_ocr(self, document_type: str, image_base64: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Smart OCR - Extract and verify data from documents
        
        Args:
            document_type: Document type (pan, aadhaar, driving_license, etc.)
            image_base64: Base64 encoded document image
            verification_id: Optional verification ID
            vendor: Vendor to use (optional)
        
        Returns:
            Verification response with extracted data
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                response = self.cashfree_client.smart_ocr(
                    document_type=document_type,
                    image_base64=image_base64,
                    verification_id=verification_id,
                    **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
                )
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
            
            return self._standardize_response(response, vendor)
        
        except Exception as e:
            raise e
    
    # ============================================================================
    # ADVANCED AADHAAR APIs
    # ============================================================================
    
    def verify_aadhaar_ocr(self, image_base64: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Aadhaar OCR - Extract data from Aadhaar card image"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_aadhaar_ocr(
                image_base64=image_base64,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def verify_aadhaar_masking(self, aadhaar_number: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Aadhaar Masking - Mask Aadhaar number for privacy"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_aadhaar_masking(
                aadhaar_number=aadhaar_number,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def offline_aadhaar_send_otp(self, aadhaar_number: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Offline Aadhaar - Send OTP to registered mobile"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.offline_aadhaar_send_otp(
                aadhaar_number=aadhaar_number,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def offline_aadhaar_verify_otp(self, otp: str, verification_id: str, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Offline Aadhaar - Verify OTP and get Aadhaar details"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.offline_aadhaar_verify_otp(
                otp=otp,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    # ============================================================================
    # ADVANCED PAN APIs
    # ============================================================================
    
    def verify_pan_advance(self, pan_number: str, name: Optional[str] = None, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """PAN Advance - Get detailed PAN information including address"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_pan_advance(
                pan_number=pan_number,
                name=name,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def verify_pan_ocr(self, image_base64: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """PAN OCR - Extract data from PAN card image"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_pan_ocr(
                image_base64=image_base64,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def verify_pan_to_gstin(self, pan_number: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """PAN to GSTIN - Get all GSTINs associated with a PAN"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_pan_to_gstin(
                pan_number=pan_number,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def verify_pan_bulk(self, pan_entries: list, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Bulk PAN Verification - Verify multiple PANs in a single request"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_pan_bulk(
                pan_entries=pan_entries,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    # ============================================================================
    # DIGILOCKER APIs
    # ============================================================================
    
    def digilocker_create_url(self, redirect_url: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """DigiLocker - Create URL for user to authenticate and share documents"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.digilocker_create_url(
                redirect_url=redirect_url,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def digilocker_get_status(self, verification_id: str, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """DigiLocker - Get verification status"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.digilocker_get_status(
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def digilocker_get_document(self, verification_id: str, document_type: str, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """DigiLocker - Get specific document from DigiLocker"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.digilocker_get_document(
                verification_id=verification_id,
                document_type=document_type,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    # ============================================================================
    # E-SIGN APIs
    # ============================================================================
    
    def esign_create_signature(self, document_base64: str, signers: list, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """E-sign - Create signature request for document"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.esign_create_signature(
                document_base64=document_base64,
                signers=signers,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def esign_get_status(self, verification_id: str, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """E-sign - Get signature status"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.esign_get_status(
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def esign_upload_document(self, document_base64: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """E-sign - Upload document for signing"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.esign_upload_document(
                document_base64=document_base64,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    # ============================================================================
    # ADVANCED VERIFICATION APIs
    # ============================================================================
    
    def verify_advance_employment(self, uan: Optional[str] = None, pan: Optional[str] = None, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Advance Employment - Get employment details from EPFO/UAN"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_advance_employment(
                uan=uan,
                pan=pan,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def verify_reverse_penny_drop(self, account_number: str, ifsc_code: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Reverse Penny Drop - Verify bank account by depositing small amount"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_reverse_penny_drop(
                account_number=account_number,
                ifsc_code=ifsc_code,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def get_reverse_penny_drop_status(self, verification_id: str, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Reverse Penny Drop - Get transaction status"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.get_reverse_penny_drop_status(
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def verify_reverse_geocoding(self, latitude: float, longitude: float, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """Reverse Geocoding - Get address from coordinates"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_reverse_geocoding(
                latitude=latitude,
                longitude=longitude,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def verify_ip_address(self, ip_address: str, verification_id: Optional[str] = None, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """IP Verification - Verify IP address location and details"""
        vendor = vendor or self.preferred_vendor
        if vendor == VerificationVendor.CASHFREE:
            response = self.cashfree_client.verify_ip_address(
                ip_address=ip_address,
                verification_id=verification_id,
                **{k: v for k, v in kwargs.items() if k in ['user_id', 'request_id', 'client_ip', 'user_agent']}
            )
            return self._standardize_response(response, vendor)
        raise ValueError(f"Unknown vendor: {vendor}")
    
    def test_connection(self, vendor: Optional[VerificationVendor] = None, **kwargs) -> Dict:
        """
        Test API connection
        
        Args:
            vendor: Vendor to use (optional)
            **kwargs: Logging parameters (user_id, request_id, client_ip, user_agent)
        
        Returns:
            Connection test response
        """
        vendor = vendor or self.preferred_vendor
        
        try:
            if vendor == VerificationVendor.CASHFREE:
                # Test connection by making a simple API call (PAN with test data)
                # This will also log the connection test
                try:
                    # Try a simple PAN verification with test data
                    test_result = self.cashfree_client.verify_pan(
                        pan_number="ABCDE1234F",
                        user_id=kwargs.get('user_id'),
                        request_id=kwargs.get('request_id'),
                        client_ip=kwargs.get('client_ip'),
                        user_agent=kwargs.get('user_agent')
                    )
                    return {
                        "status": "success",
                        "message": "Connection successful - API is responding",
                        "vendor": vendor.value,
                        "base_url": self.cashfree_client.base_url,
                        "api_version": self.cashfree_client.api_version
                    }
                except Exception as api_error:
                    # Even if API call fails, connection was attempted
                    return {
                        "status": "error",
                        "message": f"Connection attempted but API returned error: {str(api_error)}",
                        "vendor": vendor.value,
                        "base_url": self.cashfree_client.base_url,
                        "api_version": self.cashfree_client.api_version
                    }
            else:
                raise ValueError(f"Unknown vendor: {vendor}")
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "vendor": vendor.value
            }
    
    def _standardize_response(self, response: Dict, vendor: VerificationVendor) -> Dict:
        """
        Standardize vendor response to common format
        
        Args:
            response: Vendor-specific response
            vendor: Vendor used
        
        Returns:
            Standardized response dict
        """
        standardized = {
            'vendor': vendor.value,
            'raw_response': response,
            'status': 'unknown',
            'verified': False,
            'message': '',
            'details': {}
        }
        
        # Extract common fields based on vendor
        if vendor == VerificationVendor.CASHFREE:
            # Standardize Cashfree VRS API response
            # Cashfree responses have different structures based on API type
            
            # Common fields across most APIs
            status = response.get('status', response.get('valid', None))
            if status:
                standardized['status'] = str(status).upper()
                # VALID/SUCCESS means verified, INVALID/FAILED means not verified
                standardized['verified'] = status in ['VALID', 'SUCCESS', True]
            
            # Message field
            standardized['message'] = response.get('message', '')
            
            # Reference ID (common in Cashfree responses)
            if 'reference_id' in response:
                standardized['reference_id'] = response.get('reference_id')
            
            # Verification ID (if present)
            if 'verification_id' in response:
                standardized['verification_id'] = response.get('verification_id')
            
            # For PAN verification
            if 'valid' in response:
                standardized['verified'] = response.get('valid', False)
                standardized['status'] = 'VALID' if response.get('valid') else 'INVALID'
            
            # For Bank Account verification
            if 'account_status' in response:
                standardized['verified'] = response.get('account_status') == 'VALID'
                standardized['status'] = response.get('account_status', 'UNKNOWN')
            
            # For GST verification
            if 'valid' in response and 'GSTIN' in response:
                standardized['verified'] = response.get('valid', False)
                standardized['status'] = 'VALID' if response.get('valid') else 'INVALID'
            
            # All other details
            standardized['details'] = response
        else:
            # Handle other vendors
            standardized['status'] = response.get('status', 'unknown')
            standardized['verified'] = response.get('verified', False)
            standardized['message'] = response.get('message', '')
            standardized['details'] = response.get('details', {})
        
        return standardized
    
    def get_available_vendors(self) -> List[str]:
        """
        Get list of available verification vendors
        
        Returns:
            List of vendor names
        """
        return [vendor.value for vendor in VerificationVendor]
