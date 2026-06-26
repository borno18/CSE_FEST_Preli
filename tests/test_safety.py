import pytest
from app.rules import check_phishing_signals, clean_customer_reply, clean_recommended_action

def test_phishing_precheck_signals():
    """Verify that phishing words and impersonations trigger check_phishing_signals."""
    assert check_phishing_signals("Please tell me your OTP number immediately") is True
    assert check_phishing_signals("আপনার PIN নাম্বারটি দিন") is True
    assert check_phishing_signals("What is your password?") is True
    assert check_phishing_signals("Is this official bKash support desk agent?") is True
    assert check_phishing_signals("I want to know if this call from agent is safe.") is True
    
    # Safe support queries
    assert check_phishing_signals("I sent BDT 5000 to a wrong number.") is False
    assert check_phishing_signals("App crashes when opening history.") is False

def test_clean_customer_reply_asking_credentials():
    """Verify customer_reply does not leak credential requests or asks for PIN/OTP/Password."""
    # Attempting to ask for OTP is unsafe
    unsafe_reply_otp = "Please provide the OTP you received to verify your identity."
    safe_version = clean_customer_reply(unsafe_reply_otp, "phishing_or_social_engineering")
    assert "do not share your PIN, OTP, or password" in safe_version
    
    # Attempting to ask for PIN in Bangla
    unsafe_reply_bn = "দয়া করে আপনার পিন নাম্বারটি বলুন।"
    safe_version_bn = clean_customer_reply(unsafe_reply_bn, "wrong_transfer", language="bn")
    # Must use the exact copy of string from rules.py to match Unicode representations
    assert "পিন (PIN) বা ওটিপি (OTP) শেয়ার করবেন না" in safe_version_bn

def test_clean_customer_reply_unauthorized_promises():
    """Verify customer_reply does not promise direct refunds or reversals."""
    # Unsafe refund promises
    unsafe_reply_refund = "We will refund you 500 BDT within 3 business days."
    safe_version = clean_customer_reply(unsafe_reply_refund, "refund_request")
    assert "Any eligible amount will be returned through official channels after review." in safe_version
    
    # Unsafe reversal in Bangla
    unsafe_reply_rev_bn = "আমরা আপনার টাকা রিফান্ড করে দিচ্ছি।"
    safe_version_bn = clean_customer_reply(unsafe_reply_rev_bn, "payment_failed", language="bn")
    assert "যেকোনো যোগ্য অর্থ যাচাইকরণের পর অফিসিয়াল চ্যানেলের মাধ্যমে ফেরত দেওয়া হবে" in safe_version_bn

def test_clean_customer_reply_unofficial_routing():
    """Verify customer_reply does not direct customers to call arbitrary personal phone numbers."""
    unsafe_reply = "Please call 01712345678 immediately to solve your case."
    safe_version = clean_customer_reply(unsafe_reply, "other")
    assert "contact our official support hotline at 16247" in safe_version

def test_clean_recommended_action_promises():
    """Verify recommended_next_action does not contain unauthorized promises."""
    unsafe_action = "Initiate immediate refund to customer and unblock account."
    safe_version = clean_recommended_action(unsafe_action)
    assert "Do not promise a refund directly" in safe_version
