import re
import time
from bson.decimal128 import Decimal128
from database import eco_col
from discord.ext import commands

# Fields that hold economy amounts. These are stored as BSON Decimal128
# instead of plain ints so a single account can hold far more than Mongo's
# 8-byte (int64) integer ceiling (~9.22 quintillion) without overflowing or
# corrupting data. Decimal128 supports values up to roughly 10^6144.
CURRENCY_FIELDS = ("wallet", "bank", "loan_amount", "interest_accrued")


def to_decimal128(amount) -> Decimal128:
    """Converts a Python int/float/Decimal amount into a BSON Decimal128,
    suitable for use inside a Mongo $inc/$set on a currency field."""
    return Decimal128(str(int(amount)))


def _from_stored_number(value) -> int:
    """Converts a value read back from Mongo (which may be a plain int, a
    float from old data, or a Decimal128) into a plain Python int. Python
    ints have no size limit, so nothing is lost here."""
    if isinstance(value, Decimal128):
        return int(value.to_decimal())
    if value is None:
        return 0
    return int(value)


def normalize_economy_doc(doc: dict) -> dict:
    """Converts any Decimal128 currency fields on a raw economy document
    into plain ints, in place. Call this on any document read directly via
    eco_col.find()/find_one() (get_user_data already does this)."""
    if not doc:
        return doc
    for field in CURRENCY_FIELDS:
        if field in doc:
            doc[field] = _from_stored_number(doc[field])
    return doc


class JailCheckError(commands.CheckFailure):
    """Raised by the global jail check so it can be suppressed distinctly."""
    pass


def get_user_data(user_id: str) -> dict:
    user = eco_col.find_one({"_id": user_id})

    if not user:
        user = {"_id": user_id, "wallet": 0, "bank": 0, "credit_score": 0}
        eco_col.insert_one(user)

    if "balance" in user:
        wallet_amount = _from_stored_number(user.get("balance", 0))
        eco_col.update_one(
            {"_id": user_id},
            {"$set": {"wallet": to_decimal128(wallet_amount), "bank": to_decimal128(0)}, "$unset": {"balance": ""}},
        )
        user["wallet"] = wallet_amount
        user["bank"] = 0

    return normalize_economy_doc(user)


_AMOUNT_SUFFIX_MULTIPLIERS = {
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
    "t": 1_000_000_000_000,
    "q": 1_000_000_000_000_000,
}

# e.g. "100k", "2.5m", "1t"
_AMOUNT_SUFFIX_PATTERN = re.compile(r"^([+-]?\d+(?:\.\d+)?)([kmbtq])$")

# e.g. "3.72691629e-7", "1.2e9", "-4E3"
_AMOUNT_SCIENTIFIC_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?e[+-]?\d+$")


def parse_economy_amount(amount_input: str, max_balance: int) -> int:
    """
    Parses a user-supplied economy amount into an int.

    Accepts, in addition to plain integers:
      - "all" / "half" / "max" (aliases for the current max_balance)
      - thousands separators, e.g. "1,000,000"
      - shorthand suffixes: k=thousand, m=million, b=billion, t=trillion,
        q=quadrillion, e.g. "100k", "2.5m", "1t"
      - scientific notation, e.g. "3.72691629e-7", "1.2e9"

    There is no upper limit on the size of number this can parse; callers
    are responsible for clamping the result against MAX_ECONOMY_AMOUNT
    before storing it. Returns -1 if the input cannot be parsed at all.
    """
    amount_input = str(amount_input).lower().strip().replace(",", "").replace(" ", "")
    if amount_input in ("all", "max"):
        return max_balance
    if amount_input == "half":
        return max(1, max_balance // 2)
    if not amount_input:
        return -1

    try:
        suffix_match = _AMOUNT_SUFFIX_PATTERN.match(amount_input)
        if suffix_match:
            value, suffix = suffix_match.groups()
            return int(float(value) * _AMOUNT_SUFFIX_MULTIPLIERS[suffix])

        if _AMOUNT_SCIENTIFIC_PATTERN.match(amount_input):
            return int(float(amount_input))

        return int(float(amount_input))
    except (ValueError, OverflowError):
        return -1


def get_wallet(user_id: str) -> int:
    return get_user_data(user_id)["wallet"]


def get_bank(user_id: str) -> int:
    return get_user_data(user_id)["bank"]


def update_wallet(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": to_decimal128(amount)}}, upsert=True)


def update_bank(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"bank": to_decimal128(amount)}}, upsert=True)


def get_debt(user_id: str) -> int:
    user_data = get_user_data(user_id)
    loan = user_data.get("loan_amount", 0)
    interest = user_data.get("interest_accrued", 0)
    
    # Calculate pending interest since last update (dynamic view)
    if loan > 0:
        import time
        now = time.time()
        last_calc = user_data.get("last_interest_calc", now)
        time_diff = now - last_calc
        if time_diff >= 3600:
            pending = int(loan * 0.02 * (time_diff / 86400))
            interest += pending
            
    return loan + interest


def update_loan(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"loan_amount": to_decimal128(amount)}}, upsert=True)


def update_interest(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"interest_accrued": to_decimal128(amount)}}, upsert=True)


def get_prestige_level(net_worth: int) -> int:
    from config import PRESTIGE_LEVELS
    current_level = 0
    for level, data in PRESTIGE_LEVELS.items():
        if net_worth >= data["threshold"]:
            current_level = level
    return current_level

def apply_amortization(user_id: str, income: int) -> int:
    """
    Apply 30% of the given income towards any outstanding debt atomically.
    Returns the net amount the user receives after the debt payment.
    """
    user_data = get_user_data(user_id)
    loan = user_data.get("loan_amount", 0)
    interest = user_data.get("interest_accrued", 0)
    debt = loan + interest
    
    if debt <= 0:
        return income

    payment = int(income * 0.3)
    if payment > debt:
        payment = debt

    if payment <= interest:
        # Payment covers accrued interest only
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"interest_accrued": to_decimal128(-payment)}}
        )
    else:
        # Payment covers all accrued interest and a portion of the principal
        remaining_payment = payment - interest
        eco_col.update_one(
            {"_id": user_id},
            {
                "$inc": {
                    "interest_accrued": to_decimal128(-interest),
                    "loan_amount": to_decimal128(-remaining_payment)
                }
            }
        )

    return income - payment


# ---------------------------------------------------------------------------
# Jail system
# ---------------------------------------------------------------------------

JAIL_DURATION = 5400  # 90 minutes in seconds


def set_jail(user_id: str, duration: int = JAIL_DURATION) -> int:
    """Put a user in jail for `duration` seconds. Returns the release timestamp."""
    release_at = int(time.time() + duration)
    eco_col.update_one(
        {"_id": user_id},
        {"$set": {"jailed_until": release_at}},
        upsert=True,
    )
    return release_at


def is_jailed(user_id: str) -> int:
    """Return the jail release timestamp if the user is currently jailed, else 0."""
    user = eco_col.find_one({"_id": user_id}, {"jailed_until": 1})
    if not user:
        return 0
    release = user.get("jailed_until", 0)
    return release if release > time.time() else 0
