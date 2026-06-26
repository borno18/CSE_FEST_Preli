import re

# Phishing and credential patterns for pre-check (untrusted customer complaint)
PHISHING_REGEXES = [
    re.compile(r"(?i)\b(?:otp|one[- ]time[- ]password|ওয়ান[- ]টাইম[- ]পাসওয়ার্ড)\b"),
    re.compile(r"(?i)\b(?:pin|পিন)\b"),
    re.compile(r"(?i)\b(?:password|পাসওয়ার্ড)\b"),
    re.compile(r"(?i)\b(?:cvv|cvc|cvv2)\b"),
    re.compile(r"(?i)(?:card[- ]number|কার্ড[- ]নাম্বার)"),
    re.compile(r"(?i)(?:is\s*this\s*bkash|bKash\s*ki|বিকাশ\s*কি|বিকাশ\s*নাকি|বিকাশ\s*বলছেন)"),
    re.compile(
        r"(?i)(?:bKash[- ]agent|customer[- ]care|support[- ]representative|support[- ]officer|বিকাশ[- ]অফিসার|বিকাশ[- ]প্রতিনিধি|হেল্প[- ]ডেস্ক|help[- ]desk|বিকাশ[- ]হেল্প|bkash[- ]help|বিকাশ[- ]সাপোর্ট|bkash[- ]support|representative|officer)"
    ),
    re.compile(r"(?i)(?:call\s+from\s+agent|agent\s+call|এজেন্ট\s+কল|এজেন্ট\s+থেকে\s+কল)")
]

# Sensitive credentials keywords for post-processing safety filter
CREDENTIALS_KEYWORDS = [
    re.compile(r"(?i)\b(?:otp|one[- ]time[- ]password|ওয়ান[- ]টাইম[- ]পাসওয়ার্ড)\b"),
    re.compile(r"(?i)\b(?:pin|পিন)\b"),
    re.compile(r"(?i)\b(?:password|পাসওয়ার্ড)\b"),
    re.compile(r"(?i)\b(?:cvv|cvc)\b"),
]

# Safe warning pattern to allow credential keywords only if framed as a warning
SAFE_WARNING_PATTERN = re.compile(
    r"(?i)(?:never\s+share|do\s+not\s+share|don\'t\s+share|not\s+share|never\s+ask|will\s+never\s+ask|should\s+not\s+share|avoid\s+sharing|শেয়ার\s+করবেন\s+না|শেয়ার\s+না\s+করতে|বলবেন\s+না|কাউকে\s+দেবেন\s+না|কখনোই\s+দেবেন\s+না|কখনো\s+শেয়ার\s+করবেন\s+না|শেয়ার\s+করবেন\s+না)"
)

# Unsafe promise patterns (Rule 2)
PROMISE_REGEXES = [
    re.compile(r"(?i)\b(?:we\s+will\s+refund|refund\s+you|your\s+money\s+has\s+been\s+returned|we\s+will\s+reverse|your\s+account\s+is\s+unblocked|we\s+have\s+processed\s+your\s+refund|you\s+are\s+recovered|refund\s+has\s+been\s+processed|reversal\s+has\s+been\s+processed|return\s+your\s+money|will\s+be\s+credited\s+back|credited\s+to\s+your\s+account|has\s+been\s+refunded)\b"),
    re.compile(r"(?i)(?:টাকা\s+ফেরত\s+দেওয়া\s+হয়েছে|টাকা\s+রিফান্ড\s+করা\s+হবে|টাকা\s+ফেরত\s+পাবেন|রিফান্ড\s+করে\s+দেওয়া\s+হবে|অ্যাকাউন্ট\s+আনব্লক\s+করা\s+হয়েছে|টাকা\s+ফেরত\s+দিচ্ছি|রিফান্ড\s+করে\s+দিচ্ছি|রিফান্ড\s+করব|টাকা\s+ফেরত\s+দেয়া\s+হবে|রিফান্ড\s+করে\s+দেয়া\s+হবে)"),
    re.compile(r"(?i)\b(?:initiate\s+(?:immediate\s+)?refund|refund\s+the\s+customer|reverse\s+the\s+transaction|unblock\s+the\s+account|process\s+refund|immediate\s+refund)\b")
]


# Unsafe third-party contact directing (Rule 3)
# We ban raw phone numbers or links in reply that are not official (usually 16247 or 16247-based helplines)
# We match raw 11-digit or international mobile numbers to prevent directing the customer to call the scammer back.
MOBILE_NUMBER_REGEX = re.compile(r"\b(?:\+?88)?01[3-9]\d{8}\b")

# Card/account numbers (13-19 digits run)
CARD_NUMBER_RUN = re.compile(r"\b(?:\d[\s-]*){13,19}\b")

def check_phishing_signals(message: str) -> bool:
    """Scan untrusted complaint for potential phishing/social engineering indicators."""
    for pattern in PHISHING_REGEXES:
        if pattern.search(message):
            return True
    return False

def clean_customer_reply(reply: str, case_type: str, language: str = "en") -> str:
    """
    Apply a deterministic safety filter to customer_reply.
    Returns a safe substitute if any safety rule is violated.
    """
    # 1. Rule 1: No credential asking. If credential keywords appear, verify warning pattern exists.
    has_credentials = False
    for pattern in CREDENTIALS_KEYWORDS:
        if pattern.search(reply):
            has_credentials = True
            break
            
    if CARD_NUMBER_RUN.search(reply):
        has_credentials = True

    # If it contains credentials keywords but lacks a clear warning pattern, it is unsafe
    if has_credentials and not SAFE_WARNING_PATTERN.search(reply):
        if language == "bn":
            return "আপনার অভিযোগটি নথিভুক্ত করা হয়েছে। অনুগ্রহ করে কারো সাথে আপনার পিন (PIN) বা ওটিপি (OTP) শেয়ার করবেন না। আমাদের টিম আপনার টিকিটটি পর্যালোচনা করবে এবং অফিসিয়াল চ্যানেলের মাধ্যমে যোগাযোগ করবে।"
        return "We have noted your concern. Please do not share your PIN, OTP, or password with anyone. Our support team will review your case and contact you through official support channels."

    # 2. Rule 2: Refund/reversal promise check
    for pattern in PROMISE_REGEXES:
        if pattern.search(reply):
            if language == "bn":
                return "আমরা আপনার অনুরোধটি পেয়েছি। যেকোনো যোগ্য অর্থ যাচাইকরণের পর অফিসিয়াল চ্যানেলের মাধ্যমে ফেরত দেওয়া হবে। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
            return "We have received your request. Any eligible amount will be returned through official channels after review. Please do not share your PIN or OTP with anyone."

    # 3. Rule 3: Directing to suspicious numbers
    # If the reply contains an 11-digit mobile number, check if it's directing them to call/contact it.
    if MOBILE_NUMBER_REGEX.search(reply):
        # We substitute to prevent sharing unofficial phone numbers
        if language == "bn":
            return "অনুগ্রহ করে আমাদের অফিসিয়াল হেল্পলাইন ১৬২৪৭ এ যোগাযোগ করুন অথবা অ্যাপের ভেতরের সাপোর্ট চ্যাট ব্যবহার করুন। কোনো ব্যক্তিগত নম্বরে যোগাযোগ করবেন না।"
        return "Please contact our official support hotline at 16247 or use the in-app support chat for assistance. Do not contact any unofficial numbers."

    return reply

def clean_recommended_action(action: str) -> str:
    """
    Harden recommended_next_action against unsafe promises.
    """
    for pattern in PROMISE_REGEXES:
        if pattern.search(action):
            return "Verify transaction details with the customer and escalate to the dispute resolution team for verification. Do not promise a refund directly."
    return action
