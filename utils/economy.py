import time
from database import eco_col
from discord.ext import commands


class JailCheckError(commands.CheckFailure):
    """Raised by the global jail check so it can be suppressed distinctly."""
    pass


def get_user_data(user_id: str) -> dict:
    user = eco_col.find_one({"_id": user_id})

    if not user:
        user = {"_id": user_id, "wallet": 0, "bank": 0, "credit_score": 0}
        eco_col.insert_one(user)

    if "balance" in user:
        wallet_amount = user.get("balance", 0)
        eco_col.update_one(
            {"_id": user_id},
            {"$set": {"wallet": wallet_amount, "bank": 0}, "$unset": {"balance": ""}},
        )
        user["wallet"] = wallet_amount
        user["bank"] = 0

    return user


def parse_economy_amount(amount_input: str, max_balance: int) -> int:
    amount_input = str(amount_input).lower().strip()
    if amount_input == "all":
        return max_balance
    if amount_input == "half":
        return max(1, max_balance // 2)
    try:
        return int(amount_input)
    except ValueError:
        return -1


def get_wallet(user_id: str) -> int:
    return get_user_data(user_id)["wallet"]


def get_bank(user_id: str) -> int:
    return get_user_data(user_id)["bank"]


def update_wallet(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": amount}}, upsert=True)


def update_bank(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"bank": amount}}, upsert=True)


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
    eco_col.update_one({"_id": user_id}, {"$inc": {"loan_amount": amount}}, upsert=True)


def update_interest(user_id: str, amount: int) -> None:
    eco_col.update_one({"_id": user_id}, {"$inc": {"interest_accrued": amount}}, upsert=True)


def get_prestige_level(net_worth: int) -> int:
    from config import PRESTIGE_LEVELS
    current_level = 0
    for level, data in PRESTIGE_LEVELS.items():
        if net_worth >= data["threshold"]:
            current_level = level
    return current_level

def apply_amortization(user_id: str, income: int) -> int:
    """
    Aplica un porcentaje del ingreso a la deuda pendiente de forma atómica.
    Retorna la cantidad neta que le queda al usuario después del pago.
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
        # Pago solo afecta a intereses
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"interest_accrued": -payment}}
        )
    else:
        # Pago cubre todos los intereses y parte del principal
        remaining_payment = payment - interest
        eco_col.update_one(
            {"_id": user_id},
            {
                "$inc": {
                    "interest_accrued": -interest,
                    "loan_amount": -remaining_payment
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
