#!/bin/bash
# Mobikwik BBPS UAT Test Script
# Run with: bash scripts/run_mobikwik_uat_tests.sh
# Ensure MOBIKWIK_BBPS_UAT_VERBOSE_LOG=True and credentials in .env

set -e
cd "$(dirname "$0")/../backend"

echo "=== Mobikwik BBPS UAT Tests ==="
echo ""

echo "1. Token + Balance + Operators + View Bill (full test)"
python manage.py test_mobikwik_bbps --view-bill
echo ""

echo "2. View Bill only (Mobikwik UAT samples)"
python manage.py test_mobikwik_bbps --view-bill-only
echo ""

echo "3. Sanitized View Bill log (safe for email)"
python manage.py mobikwik_bbps_sanitized_log
echo ""

echo "=== Done. Check LogEntry (category mobikwik_bbps) at /logs/ ==="
