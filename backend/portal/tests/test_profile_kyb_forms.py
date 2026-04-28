from django.test import SimpleTestCase

from portal.forms import ProfileUpdateForm
from portal.models import Profile


class ProfileKYBFormTests(SimpleTestCase):
    def _base_data(self, **overrides):
        data = {
            "first_name": "Test",
            "middle_name": "",
            "last_name": "User",
            "date_of_birth": "",
            "gender": "",
            "marital_status": "",
            "nationality": "Indian",
            "country_of_residence": "India",
            "state": "",
            "city": "",
            "pincode": "",
            "address_line_1": "",
            "address_line_2": "",
            "alternate_phone": "",
            "bank_name": "",
            "account_holder_name": "",
            "account_number": "",
            "ifsc_code": "",
            "branch_name": "",
            "account_type": "",
            "pan_number": "",
            "aadhaar_number": "",
            "gst_number": "",
            "tax_id": "",
            "type": "individual",
            "business_name": "",
            "business_registration_number": "",
            "business_type": "",
            "language_preference": "en",
            "timezone": "Asia/Kolkata",
            "currency_preference": "INR",
            "recovery_email": "",
        }
        data.update(overrides)
        return data

    def test_individual_profile_clears_kyb_fields(self):
        form = ProfileUpdateForm(
            data=self._base_data(
                business_name="Acme Pvt Ltd",
                business_registration_number="CIN123",
                business_type="Pvt Ltd",
                gst_number="29ABCDE1234F1Z5",
                tax_id="TAX-1",
            ),
            instance=Profile(email="test@example.com", phone="919876543210"),
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["business_name"])
        self.assertIsNone(form.cleaned_data["business_registration_number"])
        self.assertIsNone(form.cleaned_data["business_type"])
        self.assertIsNone(form.cleaned_data["gst_number"])
        self.assertIsNone(form.cleaned_data["tax_id"])

    def test_corporate_profile_requires_business_name(self):
        form = ProfileUpdateForm(
            data=self._base_data(type="corporate"),
            instance=Profile(email="test@example.com", phone="919876543210"),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("business_name", form.errors)
