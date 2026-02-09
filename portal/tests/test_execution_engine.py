"""
Unit tests for ServiceExecutionEngine: missing handler, step failure, context propagation.
"""
import pytest
from django.contrib.auth import get_user_model

from portal.models import Service, ApiVendor, VendorApi, ServiceFlowStep
from portal.services.execution_engine import ServiceExecutionEngine

User = get_user_model()


def _make_service(code='FLOW1', name='Flow Service 1'):
    return Service.objects.get_or_create(
        code=code,
        defaults={'name': name, 'status': 'active', 'is_enabled': True}
    )[0]


def _make_vendor(code='mockvendor', name='Mock Vendor'):
    return ApiVendor.objects.get_or_create(
        code=code,
        defaults={'name': name, 'is_active': True}
    )[0]


def _make_vendor_api(vendor, api_code='step1', name='Step One'):
    return VendorApi.objects.get_or_create(
        vendor=vendor,
        api_code=api_code,
        defaults={'name': name, 'api_type': 'TRANSACTION', 'is_active': True}
    )[0]


def _make_flow_step(service, vendor, vendor_api, step_order=1, step_name='Step 1', halt_on_failure=True, is_mandatory=True):
    return ServiceFlowStep.objects.create(
        service=service,
        vendor=vendor,
        vendor_api=vendor_api,
        step_order=step_order,
        step_name=step_name,
        halt_on_failure=halt_on_failure,
        is_mandatory=is_mandatory,
    )


@pytest.mark.django_db
class TestServiceExecutionEngine:
    """Execution engine: service not found, no steps, handler missing, step failure, context."""

    def test_service_not_found(self):
        """Unknown service_code returns success=False, error=service_not_found."""
        engine = ServiceExecutionEngine()
        result = engine.execute(service_code='NONEXISTENT', payload={})
        assert result['success'] is False
        assert result.get('error') == 'service_not_found'
        assert 'not found' in (result.get('message') or '')

    def test_no_flow_defined(self):
        """Service with no flow steps returns success=False, error=no_flow_defined."""
        service = _make_service('EMPTY', 'Empty Service')
        engine = ServiceExecutionEngine()
        result = engine.execute(service_code=service.code, payload={})
        assert result['success'] is False
        assert result.get('error') == 'no_flow_defined'

    def test_missing_handler_returns_error(self):
        """When no handler is registered for a step, step outcome has error handler_not_registered."""
        service = _make_service('MISS', 'Missing Handler Service')
        vendor = _make_vendor('novendor', 'No Vendor')
        api = _make_vendor_api(vendor, 'noapi', 'No API')
        _make_flow_step(service, vendor, api, step_order=1, step_name='Missing', halt_on_failure=True, is_mandatory=True)
        engine = ServiceExecutionEngine()
        result = engine.execute(service_code=service.code, payload={})
        assert result['success'] is False
        assert result.get('error') == 'handler_not_registered'
        assert len(result.get('step_results', [])) == 1
        assert result['step_results'][0].get('error') == 'handler_not_registered'

    def test_mandatory_step_failure_stops_execution(self):
        """When a step fails and halt_on_failure is True, execution stops and returns failure."""
        service = _make_service('HALT', 'Halt Service')
        vendor = _make_vendor('failvendor', 'Fail Vendor')
        api = _make_vendor_api(vendor, 'failapi', 'Fail API')
        _make_flow_step(service, vendor, api, step_order=1, step_name='FailStep', halt_on_failure=True)

        def failing_handler(step, context, payload):
            return {"success": False, "result": None, "error": "Intentional failure"}

        engine = ServiceExecutionEngine()
        engine.register(vendor.code, api.api_code, failing_handler)
        result = engine.execute(service_code=service.code, payload={})
        assert result['success'] is False
        assert 'Intentional failure' in (result.get('error') or result.get('message') or '')
        assert len(result['step_results']) == 1

    def test_non_mandatory_step_failure_continues(self):
        """When a step fails but halt_on_failure is False, execution continues to next step."""
        service = _make_service('CONT', 'Continue Service')
        vendor = _make_vendor('contvendor', 'Cont Vendor')
        api1 = _make_vendor_api(vendor, 'failapi', 'Fail API')
        api2 = _make_vendor_api(vendor, 'okapi', 'OK API')
        _make_flow_step(service, vendor, api1, step_order=1, step_name='Fail', halt_on_failure=False)
        _make_flow_step(service, vendor, api2, step_order=2, step_name='OK', halt_on_failure=True)

        def fail_handler(step, context, payload):
            return {"success": False, "result": None, "error": "Step failed"}

        def ok_handler(step, context, payload):
            return {"success": True, "result": {"done": True}, "error": None}

        engine = ServiceExecutionEngine()
        engine.register(vendor.code, api1.api_code, fail_handler)
        engine.register(vendor.code, api2.api_code, ok_handler)
        result = engine.execute(service_code=service.code, payload={})
        assert result['success'] is True
        assert len(result['step_results']) == 2
        assert result['step_results'][0]['success'] is False
        assert result['step_results'][1]['success'] is True
        assert result.get('final_result') == {"done": True}

    def test_context_propagation_between_steps(self):
        """Successful step results are added to context and available to later steps."""
        service = _make_service('CTX', 'Context Service')
        vendor = _make_vendor('ctxvendor', 'Ctx Vendor')
        api1 = _make_vendor_api(vendor, 'first', 'First')
        api2 = _make_vendor_api(vendor, 'second', 'Second')
        _make_flow_step(service, vendor, api1, step_order=1, step_name='First')
        _make_flow_step(service, vendor, api2, step_order=2, step_name='Second')

        def first_handler(step, context, payload):
            return {"success": True, "result": {"token": "abc123"}, "error": None}

        def second_handler(step, context, payload):
            token = (context.get("step_1") or {}).get("token") or (context.get("step_ctxvendor_first") or {}).get("token")
            return {"success": True, "result": {"received_token": token}, "error": None}

        engine = ServiceExecutionEngine()
        engine.register(vendor.code, api1.api_code, first_handler)
        engine.register(vendor.code, api2.api_code, second_handler)
        result = engine.execute(service_code=service.code, payload={})
        assert result['success'] is True
        assert result['final_result'] == {"received_token": "abc123"}
