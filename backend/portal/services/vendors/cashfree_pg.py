"""
Cashfree Payment Gateway (PG) API client
Based on Cashfree PG SDK: https://github.com/cashfree/cashfree-pg-sdk-python
Documentation: https://docs.cashfree.com/reference/pg-new-apis-endpoint
"""
import time
from typing import Optional, Dict, Any, List
from core.config import payswap_config

try:
    from cashfree_pg.api_client import Cashfree
    from cashfree_pg.models.create_order_request import CreateOrderRequest
    from cashfree_pg.models.customer_details import CustomerDetails
    from cashfree_pg.models.order_meta import OrderMeta
    from cashfree_pg.models.order_create_refund_request import OrderCreateRefundRequest
    CASHFREE_PG_AVAILABLE = True
except ImportError:
    CASHFREE_PG_AVAILABLE = False


class CashfreePGClient:
    """Cashfree Payment Gateway API client"""
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        partner_key: Optional[str] = None,
        client_signature: Optional[str] = None,
        partner_merchant_id: Optional[str] = None,
        environment: Optional[str] = None
    ):
        """
        Initialize Cashfree PG client
        
        Args:
            client_id: X-Client-Id
            client_secret: X-Client-Secret
            partner_key: X-Partner-Key (optional)
            client_signature: X-Client-Signature (optional)
            partner_merchant_id: X-Partner-Merchant-Id (optional)
            environment: SANDBOX or PRODUCTION
        """
        # Re-check import at runtime in case module was reloaded
        try:
            from cashfree_pg.api_client import Cashfree
            from cashfree_pg.models.create_order_request import CreateOrderRequest
            from cashfree_pg.models.customer_details import CustomerDetails
            from cashfree_pg.models.order_meta import OrderMeta
            from cashfree_pg.models.order_create_refund_request import OrderCreateRefundRequest
        except ImportError:
            raise ImportError("cashfree_pg package is not installed. Install it using: pip install cashfree_pg")
        
        # Get credentials from config or parameters
        config_client_id = getattr(payswap_config, 'CASHFREE_PG_CLIENT_ID', None)
        config_client_secret = getattr(payswap_config, 'CASHFREE_PG_CLIENT_SECRET', None)
        config_partner_key = getattr(payswap_config, 'CASHFREE_PG_PARTNER_KEY', None)
        config_client_signature = getattr(payswap_config, 'CASHFREE_PG_CLIENT_SIGNATURE', None)
        config_partner_merchant_id = getattr(payswap_config, 'CASHFREE_PG_PARTNER_MERCHANT_ID', None)
        config_environment = getattr(payswap_config, 'CASHFREE_PG_ENVIRONMENT', 'SANDBOX')
        
        # Handle SecretStr type from config
        if config_client_id:
            self.client_id = client_id or (config_client_id.get_secret_value() if hasattr(config_client_id, 'get_secret_value') else str(config_client_id))
        else:
            self.client_id = client_id
        
        if config_client_secret:
            self.client_secret = client_secret or (config_client_secret.get_secret_value() if hasattr(config_client_secret, 'get_secret_value') else str(config_client_secret))
        else:
            self.client_secret = client_secret
        
        if config_partner_key:
            self.partner_key = partner_key or (config_partner_key.get_secret_value() if hasattr(config_partner_key, 'get_secret_value') else str(config_partner_key))
        else:
            self.partner_key = partner_key
        
        if config_client_signature:
            self.client_signature = client_signature or (config_client_signature.get_secret_value() if hasattr(config_client_signature, 'get_secret_value') else str(config_client_signature))
        else:
            self.client_signature = client_signature
        
        self.partner_merchant_id = partner_merchant_id or config_partner_merchant_id
        self.environment = environment or config_environment
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Cashfree PG Client ID and Client Secret are required")
        
        # Import here to ensure it's available
        from cashfree_pg.api_client import Cashfree as CashfreeClient
        
        # Initialize Cashfree SDK client
        env = CashfreeClient.PRODUCTION if self.environment.upper() == 'PRODUCTION' else CashfreeClient.SANDBOX
        
        self.client = CashfreeClient(
            XEnvironment=env,
            XClientId=self.client_id,
            XClientSecret=self.client_secret,
            XPartnerKey=self.partner_key if self.partner_key else None,
            XClientSignature=self.client_signature if self.client_signature else None,
            XPartnerMerchantId=self.partner_merchant_id if self.partner_merchant_id else None
        )
        
        self.api_version = "2023-08-01"  # Default API version

    @staticmethod
    def _is_transient_cashfree_network_error(exc: BaseException) -> bool:
        """Retry PGCreateOrder on flaky TLS / CDN drops (common in dev)."""
        msg = str(exc).lower()
        needles = (
            "connection reset",
            "connection aborted",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "errno 54",
            "broken pipe",
            "remote end closed connection",
        )
        return any(n in msg for n in needles)

    def create_order(
        self,
        order_amount: float,
        order_currency: str,
        customer_details: Dict[str, Any],
        order_meta: Optional[Dict[str, Any]] = None,
        order_id: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Create a payment order
        
        Args:
            order_amount: Order amount
            order_currency: Currency code (e.g., 'INR')
            customer_details: Customer details dict with customer_id, customer_phone, customer_email, etc.
            order_meta: Order metadata dict with return_url, etc.
            order_id: Optional custom order ID
            **kwargs: Additional order parameters
        
        Returns:
            API response dict
        """
        try:
            # Normalize phone number (remove +91 prefix, keep only 10 digits)
            normalized_customer_details = customer_details.copy()
            if 'customer_phone' in normalized_customer_details:
                phone = normalized_customer_details['customer_phone']
                # Remove +91 or 91 prefix and keep only last 10 digits
                phone = phone.replace('+91', '').replace('91', '').strip()
                if len(phone) > 10:
                    phone = phone[-10:]  # Take last 10 digits
                normalized_customer_details['customer_phone'] = phone
            
            # Create customer details object
            customer = CustomerDetails(**normalized_customer_details)
            
            # Create order meta object
            order_meta_obj = None
            if order_meta:
                order_meta_obj = OrderMeta(**order_meta)
            
            # Create order request
            order_request = CreateOrderRequest(
                order_amount=order_amount,
                order_currency=order_currency,
                customer_details=customer,
                order_meta=order_meta_obj,
                order_id=order_id,
                **kwargs
            )

            # Call API (retry transient network failures to Cashfree)
            api_response = None
            last_call_error: Optional[BaseException] = None
            for attempt in range(3):
                try:
                    api_response = self.client.PGCreateOrder(
                        self.api_version,
                        order_request,
                        None,
                        None,
                    )
                    break
                except Exception as call_err:
                    last_call_error = call_err
                    if attempt < 2 and self._is_transient_cashfree_network_error(call_err):
                        time.sleep(0.35 * (2**attempt))
                        continue
                    raise
            if api_response is None:
                raise last_call_error if last_call_error else RuntimeError("Cashfree PGCreateOrder returned no response")

            # Convert response to dict
            if hasattr(api_response, 'data') and api_response.data:
                if hasattr(api_response.data, 'to_dict'):
                    result = api_response.data.to_dict()
                elif hasattr(api_response.data, '__dict__'):
                    result = {k: v for k, v in api_response.data.__dict__.items() if not k.startswith('_')}
                else:
                    result = {'data': str(api_response.data)}
            else:
                result = {'status': 'success', 'message': 'Order created'}
            
            # Logging
            from portal.utils.logging_helper import SecureLogger
            from portal.tasks.write_logs_task import write_logs_task
            logger = SecureLogger('portal.services.vendors.cashfree_pg')
            
            log_data = {
                'action': 'cashfree_pg_create_order',
                'order_amount': order_amount,
                'order_currency': order_currency,
                'order_id': order_id,
                'result': result
            }
            
            logger.info(
                f'Cashfree PG Create Order - Amount: {order_amount} {order_currency}',
                user=None,
                extra_data=log_data
            )
            
            write_logs_task.delay(
                log_level='INFO',
                message=f'Cashfree PG Create Order - Amount: {order_amount} {order_currency} | Order ID: {order_id or "auto-generated"}',
                module_name='portal.services.vendors.cashfree_pg',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data=log_data,
                client_ip=None,
                user_agent=None,
                session_id=None
            )
            
            return result
        except Exception as e:
            # Log error
            from portal.utils.logging_helper import SecureLogger
            from portal.tasks.write_logs_task import write_logs_task
            logger = SecureLogger('portal.services.vendors.cashfree_pg')
            
            error_data = {
                'action': 'cashfree_pg_create_order_error',
                'error': str(e),
                'order_amount': order_amount,
                'order_currency': order_currency
            }
            
            logger.error(
                f'Cashfree PG Create Order Error: {str(e)}',
                user=None,
                extra_data=error_data,
                traceback=str(e)
            )
            
            write_logs_task.delay(
                log_level='ERROR',
                message=f'Cashfree PG Create Order Error: {str(e)}',
                module_name='portal.services.vendors.cashfree_pg',
                url=None,
                request_id=None,
                response_id=None,
                user_id=None,
                extra_data={**error_data, 'traceback': str(e)},
                client_ip=None,
                user_agent=None,
                session_id=None
            )
            
            raise Exception(f"Cashfree PG Create Order error: {str(e)}")
    
    def get_order(self, order_id: str) -> Dict:
        """
        Get order details
        
        Args:
            order_id: Order ID
        
        Returns:
            Order details dict
        """
        try:
            api_response = self.client.PGFetchOrder(
                self.api_version,
                order_id,
                None
            )
            
            if hasattr(api_response, 'data') and api_response.data:
                if hasattr(api_response.data, 'to_dict'):
                    result = api_response.data.to_dict()
                elif hasattr(api_response.data, '__dict__'):
                    result = {k: v for k, v in api_response.data.__dict__.items() if not k.startswith('_')}
                else:
                    result = {'data': str(api_response.data)}
            else:
                result = {'status': 'success', 'order_id': order_id}
            
            return result
        except Exception as e:
            raise Exception(f"Cashfree PG Get Order error: {str(e)}")
    
    def create_refund(
        self,
        order_id: str,
        refund_amount: float,
        refund_id: Optional[str] = None,
        refund_note: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Create a refund
        
        Args:
            order_id: Order ID
            refund_amount: Refund amount
            refund_id: Optional custom refund ID
            refund_note: Optional refund note
            **kwargs: Additional refund parameters
        
        Returns:
            Refund response dict
        """
        try:
            from cashfree_pg.models.order_create_refund_request import OrderCreateRefundRequest
            refund_request = OrderCreateRefundRequest(
                refund_amount=refund_amount,
                refund_id=refund_id,
                refund_note=refund_note,
                **kwargs
            )
            
            api_response = self.client.PGOrderCreateRefund(
                self.api_version,
                order_id,
                refund_request,
                None
            )
            
            if hasattr(api_response, 'data') and api_response.data:
                if hasattr(api_response.data, 'to_dict'):
                    result = api_response.data.to_dict()
                elif hasattr(api_response.data, '__dict__'):
                    result = {k: v for k, v in api_response.data.__dict__.items() if not k.startswith('_')}
                else:
                    result = {'data': str(api_response.data)}
            else:
                result = {'status': 'success', 'message': 'Refund created'}
            
            return result
        except Exception as e:
            raise Exception(f"Cashfree PG Create Refund error: {str(e)}")
    
    def get_refund(self, order_id: str, refund_id: str) -> Dict:
        """
        Get refund details
        
        Args:
            order_id: Order ID
            refund_id: Refund ID
        
        Returns:
            Refund details dict
        """
        try:
            api_response = self.client.PGOrderFetchRefund(
                self.api_version,
                order_id,
                refund_id,
                None
            )
            
            if hasattr(api_response, 'data') and api_response.data:
                if hasattr(api_response.data, 'to_dict'):
                    result = api_response.data.to_dict()
                elif hasattr(api_response.data, '__dict__'):
                    result = {k: v for k, v in api_response.data.__dict__.items() if not k.startswith('_')}
                else:
                    result = {'data': str(api_response.data)}
            else:
                result = {'status': 'success', 'refund_id': refund_id}
            
            return result
        except Exception as e:
            raise Exception(f"Cashfree PG Get Refund error: {str(e)}")
    
    def get_payment(self, order_id: str, cf_payment_id: Optional[str] = None) -> Dict:
        """
        Get payment details
        
        Args:
            order_id: Order ID
            cf_payment_id: Optional Cashfree payment ID (if not provided, fetches all payments for order)
        
        Returns:
            Payment details dict
        """
        try:
            # If cf_payment_id is provided, use PGOrderFetchPayment
            # Otherwise, use PGOrderFetchPayments to get all payments for the order
            if cf_payment_id:
                api_response = self.client.PGOrderFetchPayment(
                    self.api_version,
                    order_id,
                    cf_payment_id,
                    None
                )
            else:
                # Fetch all payments for the order
                api_response = self.client.PGOrderFetchPayments(
                    self.api_version,
                    order_id,
                    None
                )
            
            if hasattr(api_response, 'data') and api_response.data:
                if hasattr(api_response.data, 'to_dict'):
                    result = api_response.data.to_dict()
                elif hasattr(api_response.data, '__dict__'):
                    result = {k: v for k, v in api_response.data.__dict__.items() if not k.startswith('_')}
                else:
                    result = {'data': str(api_response.data)}
            else:
                result = {'status': 'success', 'order_id': order_id}
            
            return result
        except Exception as e:
            raise Exception(f"Cashfree PG Get Payment error: {str(e)}")
    
    def create_payment_link(
        self,
        link_amount: float,
        link_currency: str,
        link_id: Optional[str] = None,
        link_purpose: Optional[str] = None,
        customer_details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict:
        """
        Create a payment link
        
        Args:
            link_amount: Link amount
            link_currency: Currency code
            link_id: Optional custom link ID
            link_purpose: Link purpose/description
            customer_details: Optional customer details
            **kwargs: Additional parameters
        
        Returns:
            Payment link response dict
        """
        try:
            from cashfree_pg.models.create_link_request import CreateLinkRequest
            
            link_request_data = {
                'link_amount': link_amount,
                'link_currency': link_currency,
                'link_id': link_id,
                'link_purpose': link_purpose,
                **kwargs
            }
            
            if customer_details:
                link_request_data['customer_details'] = customer_details
            
            link_request = CreateLinkRequest(**link_request_data)
            
            api_response = self.client.PGCreateLink(
                self.api_version,
                link_request,
                None
            )
            
            if hasattr(api_response, 'data') and api_response.data:
                if hasattr(api_response.data, 'to_dict'):
                    result = api_response.data.to_dict()
                elif hasattr(api_response.data, '__dict__'):
                    result = {k: v for k, v in api_response.data.__dict__.items() if not k.startswith('_')}
                else:
                    result = {'data': str(api_response.data)}
            else:
                result = {'status': 'success', 'message': 'Payment link created'}
            
            return result
        except Exception as e:
            raise Exception(f"Cashfree PG Create Payment Link error: {str(e)}")
    
    def get_payment_link(self, link_id: str) -> Dict:
        """
        Get payment link details
        
        Args:
            link_id: Link ID
        
        Returns:
            Payment link details dict
        """
        try:
            api_response = self.client.PGFetchLink(
                self.api_version,
                link_id,
                None
            )
            
            if hasattr(api_response, 'data') and api_response.data:
                if hasattr(api_response.data, 'to_dict'):
                    result = api_response.data.to_dict()
                elif hasattr(api_response.data, '__dict__'):
                    result = {k: v for k, v in api_response.data.__dict__.items() if not k.startswith('_')}
                else:
                    result = {'data': str(api_response.data)}
            else:
                result = {'status': 'success', 'link_id': link_id}
            
            return result
        except Exception as e:
            raise Exception(f"Cashfree PG Get Payment Link error: {str(e)}")
