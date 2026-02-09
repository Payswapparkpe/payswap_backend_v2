#!/usr/bin/env python3
"""
Standalone script to send a test email via Parkpe SMTP.
Reads SMTP_*_Parkpe from .env in project root. No Django required.
Usage: python3 scripts/send_parkpe_test_email.py [to_email]
Default to_email: sandeep@payswap.in
"""
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def load_env(env_path=".env"):
    """Load key=value pairs from .env, skip comments and empty lines."""
    env = {}
    if not os.path.isfile(env_path):
        return env
    with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main():
    # Project root = directory containing manage.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    env_path = os.path.join(project_root, ".env")
    env = load_env(env_path)

    host = env.get("SMTP_HOST_Parkpe")
    port = int(env.get("SMTP_PORT_Parkpe", "587") or "587")
    user = env.get("SMTP_USER_Parkpe")
    password = env.get("SMTP_PASSWORD_Parkpe")
    use_tls = (env.get("SMTP_USE_TLS_Parkpe", "true") or "true").lower() in ("true", "1", "yes")
    from_email = env.get("SMTP_DEFAULT_FROM_Parkpe") or user

    to_email = (sys.argv[1] if len(sys.argv) > 1 else "sandeep@payswap.in").strip()

    if not all([host, user, password]):
        print("ERROR: Parkpe SMTP not configured. Set SMTP_HOST_Parkpe, SMTP_USER_Parkpe, SMTP_PASSWORD_Parkpe in .env")
        print(f"  Looked at: {env_path}")
        sys.exit(1)

    msg = MIMEMultipart()
    msg["Subject"] = "Payswap – Parkpe SMTP test (voucher system)"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(
        "This is a test email sent via Parkpe SMTP (Zoho). "
        "If you received this, Parkpe SMTP is working for the voucher system.",
        "plain",
    ))

    try:
        with smtplib.SMTP(host, port) as s:
            if use_tls:
                s.starttls()
            s.login(user, password)
            s.sendmail(from_email, [to_email], msg.as_string())
        print(f"SUCCESS: Test email sent to {to_email} via Parkpe SMTP.")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
