#!/usr/bin/env python3
"""
Test script to verify SMTP configuration and send a test email.
Useful for debugging password reset email delivery.

Usage:
    python test_smtp.py [recipient_email]

Example:
    python test_smtp.py user@example.com
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded config from {env_path}")
else:
    print(f"⚠ No .env file found. Using environment variables or defaults.")

# Import after loading env
from utils.emailer import send_password_reset_email

def test_smtp_config():
    """Validate SMTP configuration."""
    print("\n📧 SMTP Configuration Check:")
    print(f"  SMTP_HOST: {os.environ.get('SMTP_HOST', 'NOT SET')}")
    print(f"  SMTP_PORT: {os.environ.get('SMTP_PORT', 'NOT SET')}")
    print(f"  SMTP_USER: {os.environ.get('SMTP_USER', 'NOT SET')}")
    print(f"  SMTP_PASSWORD: {'***' if os.environ.get('SMTP_PASSWORD') else 'NOT SET'}")
    print(f"  RESET_URL_BASE: {os.environ.get('RESET_URL_BASE', 'NOT SET')}")

def test_send_email(recipient: str):
    """Send a test password reset email."""
    print(f"\n📤 Attempting to send test email to: {recipient}")
    
    # Use a dummy token for testing
    test_token = "test_token_12345abcde"
    
    success, error = send_password_reset_email(recipient, test_token)
    
    if success:
        print(f"✅ Email sent successfully!")
        print(f"   Recipient: {recipient}")
        print(f"   Reset URL would include token: {test_token}")
        return True
    else:
        print(f"❌ Failed to send email:")
        print(f"   Error: {error}")
        return False

if __name__ == "__main__":
    test_smtp_config()
    
    recipient = sys.argv[1] if len(sys.argv) > 1 else None
    
    if recipient:
        print("\nAttempting to send test email...")
        success = test_send_email(recipient)
        sys.exit(0 if success else 1)
    else:
        print("\n💡 Usage: python test_smtp.py user@example.com")
        print("   No recipient provided. Configure .env and run with an email address to test sending.")
