from api.parkpe_api.views import _extract_challan_records, _normalize_instantpay_challan_row


def test_extract_challan_records_reads_vehicle_data_shape():
    payload = {
        "statuscode": "TXN",
        "status": "Transaction Successful",
        "data": {
            "vehicleData": [
                {"challanNumber": "HR123", "challanAmount": "1000"},
                {"challanNumber": "HP456", "challanAmount": "2000"},
            ]
        },
    }

    rows = _extract_challan_records(payload)

    assert len(rows) == 2
    assert rows[0]["challanNumber"] == "HR123"
    assert rows[1]["challanNumber"] == "HP456"


def test_normalize_instantpay_vehicle_data_row_maps_required_fields():
    row = {
        "challanNumber": "HR46244250623101065",
        "challanDate": "13-06-2025",
        "challanStatus": "Pending",
        "challanAmount": "2000",
        "rcStateCode": "HR",
        "challanPlace": "Gurugram",
        "userName": "S*****P K***R",
        "offences": [
            {
                "offenceName": "Driving fast/slower than speed limits",
                "offenceFine": "2000",
                "motorVehicleAct": "Section 183",
            }
        ],
    }

    mapped = _normalize_instantpay_challan_row(row, "24BH8017B")

    assert mapped["challanNumber"] == "HR46244250623101065"
    assert mapped["vehicleNumber"] == "24BH8017B"
    assert mapped["offence"] == "Driving fast/slower than speed limits"
    assert mapped["offenceDate"] == "13-06-2025"
    assert mapped["location"] == "Gurugram"
    assert mapped["state"] == "HR"
    assert mapped["amount"] == 2000.0
    assert mapped["totalAmount"] == 2000.0
    assert mapped["status"] == "pending"
