"""
Serializers for Instantpay module endpoints.
"""
from rest_framework import serializers


class PartnerTxnSerializer(serializers.Serializer):
    partner_txn_id = serializers.CharField(max_length=64)


class AepsWithdrawSerializer(PartnerTxnSerializer):
    aadhaar = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class AepsBalanceSerializer(PartnerTxnSerializer):
    aadhaar = serializers.CharField(max_length=20)


class DmtTransferSerializer(PartnerTxnSerializer):
    beneficiary_account = serializers.CharField(max_length=32)
    ifsc = serializers.CharField(max_length=16)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class GenericVehicleSerializer(PartnerTxnSerializer):
    vehicle_number = serializers.CharField(max_length=20)


class CreditCardBillPaySerializer(PartnerTxnSerializer):
    card_number = serializers.CharField(max_length=19)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class DigiLockerInitSerializer(PartnerTxnSerializer):
    redirect_url = serializers.URLField()


class BinLookupSerializer(PartnerTxnSerializer):
    bin = serializers.CharField(max_length=8)


class CreditReportSerializer(PartnerTxnSerializer):
    pan = serializers.CharField(max_length=10)


class CreditScoreSimulatorSerializer(PartnerTxnSerializer):
    income = serializers.IntegerField(min_value=0)
    emi = serializers.IntegerField(min_value=0)


class MerchantOnboardingSerializer(PartnerTxnSerializer):
    business_name = serializers.CharField(max_length=200)
    pan = serializers.CharField(max_length=10)
