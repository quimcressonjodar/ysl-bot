import random
import time
import os
from zoneinfo import ZoneInfo
import matplotlib
# Use Agg backend for headless environments like Render
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import io
import discord
from config import STOCKS, STOCK_HISTORY_LIMIT, STOCK_FEE
from pymongo import MongoClient

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["protox_bot"]
stocks_col = db["stocks_history"]
user_stocks_col = db["user_stocks"]
stock_alerts_col = db["stock_alerts"]
autosell_col = db["stock_autosells"]
ipo_col = db["ipo_stocks"]


# ---------------------------------------------------------------------------
# IPO – load persisted custom stocks into the live STOCKS dict on startup
# ---------------------------------------------------------------------------

def load_ipo_stocks():
    """Load custom IPO stocks from MongoDB and inject them into STOCKS."""
    for doc in ipo_col.find():
        symbol = doc["symbol"]
        if symbol not in STOCKS:
            STOCKS[symbol] = {
                "name": doc["name"],
                "sector": doc.get("sector", "IPO"),
                "volatility": doc.get("volatility", 0.10),
                "initial_price": doc.get("initial_price", 500),
                "description": doc.get("description", "A new company on the market."),
            }


def add_ipo_stock(symbol: str, data: dict) -> str | None:
    """
    Add a new IPO stock to the market and remove the worst performer.
    Returns the symbol of the removed company (or None if market was empty).
    """
    worst_symbol = None
    worst_performance = float("inf")
    for s in list(STOCKS.keys()):
        try:
            price = get_current_price(s)
        except Exception:
            price = STOCKS[s]["initial_price"]
        initial = STOCKS[s].get("initial_price", 500)
        # Performance = % change from initial price (lower = worse)
        performance = (price - initial) / initial if initial else 0
        if performance < worst_performance:
            worst_performance = performance
            worst_symbol = s

    # Remove worst from live dict, price history, and IPO registry
    if worst_symbol:
        STOCKS.pop(worst_symbol, None)
        stocks_col.delete_one({"symbol": worst_symbol})
        ipo_col.delete_one({"symbol": worst_symbol})

    # Add new stock to live dict
    STOCKS[symbol] = data

    # Persist in IPO collection so it survives bot restarts
    ipo_col.update_one(
        {"symbol": symbol},
        {"$set": {"symbol": symbol, **data}},
        upsert=True,
    )

    # Seed price history with two identical points (chart needs >= 2)
    stocks_col.delete_one({"symbol": symbol})
    stocks_col.insert_one({
        "symbol": symbol,
        "prices": [
            {"price": data["initial_price"], "timestamp": time.time() - 60},
            {"price": data["initial_price"], "timestamp": time.time()},
        ],
    })

    return worst_symbol


# ---------------------------------------------------------------------------
# Price helpers
# ---------------------------------------------------------------------------

def get_current_price(symbol):
    """Get the latest price for a stock symbol."""
    history = stocks_col.find_one({"symbol": symbol})
    if not history or not history.get("prices"):
        return STOCKS[symbol]["initial_price"]
    return history["prices"][-1]["price"]


def update_stock_prices(news_impact=None):
    """Update prices for all stocks using Geometric Brownian Motion logic."""
    if news_impact is None:
        news_impact = {}

    for symbol, config in STOCKS.items():
        multiplier = news_impact.get(symbol, 1.0) * news_impact.get("ALL", 1.0)
        history = stocks_col.find_one({"symbol": symbol})
        if not history:
            prices = [{"price": config["initial_price"], "timestamp": time.time()}]
            stocks_col.insert_one({"symbol": symbol, "prices": prices})
            continue

        current_prices = history.get("prices", [])
        last_price = current_prices[-1]["price"]

        drift = 0.005
        volatility = config["volatility"]
        amplified_multiplier = 1.0 + (multiplier - 1.0) * 1.5

        change = random.normalvariate(drift, volatility)
        new_price = max(50, int(last_price * (1 + change) * amplified_multiplier))

        new_entry = {"price": new_price, "timestamp": time.time()}
        current_prices.append(new_entry)

        if len(current_prices) > STOCK_HISTORY_LIMIT:
            current_prices = current_prices[-STOCK_HISTORY_LIMIT:]

        stocks_col.update_one({"symbol": symbol}, {"$set": {"prices": current_prices}})


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

def generate_stock_chart(symbol):
    """Generate a PNG chart for a stock symbol (last 24 h only) and return as discord.File."""
    history = stocks_col.find_one({"symbol": symbol})
    if not history or len(history.get("prices", [])) < 2:
        return None

    # Keep only the last 24 hours of data; fall back to the last 2 points if needed
    cutoff = time.time() - 86400
    all_prices = history["prices"]
    recent = [p for p in all_prices if p["timestamp"] >= cutoff]
    if len(recent) < 2:
        recent = all_prices[-2:]

    spain_tz = ZoneInfo("Europe/Madrid")
    prices = [p["price"] for p in recent]
    timestamps = [
        pd.to_datetime(p["timestamp"], unit='s', utc=True).tz_convert(spain_tz)
        for p in recent
    ]

    df = pd.DataFrame({"timestamp": timestamps, "price": prices})

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))

    for i in range(len(prices) - 1):
        segment_color = '#2ecc71' if prices[i + 1] >= prices[i] else '#e74c3c'
        ax.plot(df['timestamp'][i:i + 2], df['price'][i:i + 2], color=segment_color, linewidth=2)

    trend_color = '#2ecc71' if prices[-1] >= prices[0] else '#e74c3c'
    ax.fill_between(df['timestamp'], df['price'], alpha=0.1, color=trend_color)

    ax.set_title(f"{STOCKS[symbol]['name']} ({symbol})", fontsize=16, color='white', pad=20)
    ax.set_ylabel("Price (Coins)", color='white')
    ax.grid(True, alpha=0.2)

    time_range = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
    if time_range > 86400:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M', tz=spain_tz))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=spain_tz))
    fig.autofmt_xdate(rotation=45)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)

    return discord.File(fp=buf, filename=f"{symbol}_chart.png")


# ---------------------------------------------------------------------------
# Portfolio helpers
# ---------------------------------------------------------------------------

def get_user_portfolio(user_id):
    portfolio = user_stocks_col.find_one({"_id": user_id})
    return portfolio.get("stocks", {}) if portfolio else {}


def buy_stock(user_id, symbol, quantity, price):
    portfolio = user_stocks_col.find_one({"_id": user_id})
    if not portfolio:
        user_stocks_col.insert_one({"_id": user_id, "stocks": {}})
        portfolio = {"stocks": {}}

    stocks = portfolio.get("stocks", {})
    if symbol not in stocks:
        stocks[symbol] = {"quantity": 0, "avg_price": 0}

    current = stocks[symbol]
    new_total_cost = (current["quantity"] * current["avg_price"]) + (quantity * price)
    new_quantity = current["quantity"] + quantity

    stocks[symbol] = {
        "quantity": new_quantity,
        "avg_price": new_total_cost / new_quantity,
    }

    user_stocks_col.update_one({"_id": user_id}, {"$set": {"stocks": stocks}})


def sell_stock(user_id, symbol, quantity):
    portfolio = user_stocks_col.find_one({"_id": user_id})
    if not portfolio or symbol not in portfolio.get("stocks", {}):
        return False

    stocks = portfolio["stocks"]
    if stocks[symbol]["quantity"] < quantity:
        return False

    stocks[symbol]["quantity"] -= quantity
    if stocks[symbol]["quantity"] == 0:
        del stocks[symbol]

    user_stocks_col.update_one({"_id": user_id}, {"$set": {"stocks": stocks}})
    return True


def get_dividend_rate(symbol: str) -> tuple[float, float]:
    """
    Calculate a stock's dividend rate based on its 24-hour price performance.
    Returns (rate, performance_pct) where rate is between 0.0005 and 0.02.

    Formula: rate = clamp(0.003 + performance * 0.10, 0.0005, 0.02)
    Examples:
      +10% gain  → 0.003 + 0.10*0.10 = 1.3%
      flat       → 0.3%
      -10% loss  → clamped to 0.05% (minimum)
    """
    history = stocks_col.find_one({"symbol": symbol})
    if not history or len(history.get("prices", [])) < 2:
        return 0.003, 0.0  # default base rate if no history

    prices = history["prices"]
    current_price = prices[-1]["price"]
    cutoff = time.time() - 86400  # 24 hours ago

    # Find the oldest price within the last 24h; fall back to earliest available
    price_24h_ago = None
    for entry in prices:
        if entry["timestamp"] >= cutoff:
            price_24h_ago = entry["price"]
            break
    if price_24h_ago is None:
        price_24h_ago = prices[0]["price"]

    if price_24h_ago == 0:
        return 0.003, 0.0

    performance = (current_price - price_24h_ago) / price_24h_ago
    rate = max(0.0005, min(0.02, 0.003 + performance * 0.10))
    return rate, performance


def process_dividends():
    """
    Pay proportional dividends to all shareholders.
    Each stock's rate depends on its 24h performance (0.05% – 2%).
    Returns (users_paid, total_distributed, rates_by_symbol).
    """
    from utils.economy import update_wallet

    # Pre-compute rates for every listed stock
    rates = {}
    for symbol in STOCKS:
        rate, perf = get_dividend_rate(symbol)
        rates[symbol] = {"rate": rate, "performance": perf}

    all_portfolios = user_stocks_col.find()
    total_distributed = 0
    users_paid = 0

    for portfolio in all_portfolios:
        user_id = portfolio["_id"]
        stocks_data = portfolio.get("stocks", {})
        user_total_dividend = 0

        for symbol, data in stocks_data.items():
            if symbol not in STOCKS:
                continue
            current_price = get_current_price(symbol)
            rate = rates[symbol]["rate"]
            dividend = int(current_price * data["quantity"] * rate)
            user_total_dividend += dividend

        if user_total_dividend > 0:
            update_wallet(user_id, user_total_dividend)
            total_distributed += user_total_dividend
            users_paid += 1

    return users_paid, total_distributed, rates


# ---------------------------------------------------------------------------
# Price Alert System
# ---------------------------------------------------------------------------

def add_price_alert(user_id: str, symbol: str, target_price: int) -> int:
    """
    Save a price alert. Direction is inferred from current vs target price.
    Returns the short sequential ID (1, 2, 3, ...) scoped to this user.
    """
    current_price = get_current_price(symbol)
    direction = "above" if target_price > current_price else "below"
    # Compute next short ID for this user
    existing = list(stock_alerts_col.find({"user_id": user_id}, {"seq": 1}))
    used_seqs = [a.get("seq", 0) for a in existing]
    seq = 1
    while seq in used_seqs:
        seq += 1
    stock_alerts_col.insert_one({
        "user_id": user_id,
        "seq": seq,
        "symbol": symbol,
        "target_price": target_price,
        "direction": direction,
        "created_at": time.time(),
    })
    return seq


def get_user_alerts(user_id: str) -> list:
    alerts = list(stock_alerts_col.find({"user_id": user_id}))
    # Backfill seq for legacy alerts that were created before the seq field existed
    used_seqs = {a["seq"] for a in alerts if "seq" in a}
    next_seq = 1
    for a in alerts:
        if "seq" not in a:
            while next_seq in used_seqs:
                next_seq += 1
            stock_alerts_col.update_one({"_id": a["_id"]}, {"$set": {"seq": next_seq}})
            a["seq"] = next_seq
            used_seqs.add(next_seq)
            next_seq += 1
    return sorted(alerts, key=lambda a: a["seq"])


def remove_alert_by_seq(user_id: str, seq: int) -> dict | None:
    """Delete alert by short ID. Returns the alert doc if found, else None."""
    alert = stock_alerts_col.find_one({"user_id": user_id, "seq": seq})
    if alert:
        stock_alerts_col.delete_one({"_id": alert["_id"]})
    return alert


async def check_price_alerts(bot):
    """
    Called after every stock price update.
    Sends a DM to users whose price alert has triggered, then deletes it.
    """
    alerts = list(stock_alerts_col.find())
    for alert in alerts:
        symbol = alert["symbol"]
        if symbol not in STOCKS:
            continue
        try:
            current_price = get_current_price(symbol)
        except Exception:
            continue

        triggered = (
            (alert["direction"] == "above" and current_price >= alert["target_price"]) or
            (alert["direction"] == "below" and current_price <= alert["target_price"])
        )
        if not triggered:
            continue

        try:
            user = await bot.fetch_user(int(alert["user_id"]))
            arrow = "📈" if alert["direction"] == "above" else "📉"
            verb = "reached" if alert["direction"] == "above" else "dropped to"
            color = 0x2ECC71 if alert["direction"] == "above" else 0xE74C3C
            embed = discord.Embed(
                title="🔔 Price alert triggered!",
                description=(
                    f"{arrow} **{symbol}** has {verb} your target of 🪙 **{alert['target_price']:,}**\n\n"
                    f"💹 Current price: 🪙 **{current_price:,}**"
                ),
                color=color,
            )
            embed.set_footer(text="This alert has been automatically removed.")
            await user.send(embed=embed)
        except Exception:
            pass  # DMs closed or user not found

        stock_alerts_col.delete_one({"_id": alert["_id"]})


# ---------------------------------------------------------------------------
# Auto-Sell Order System
# ---------------------------------------------------------------------------

def add_autosell(user_id: str, symbol: str, quantity: int, target_price: int) -> int:
    """
    Save an auto-sell order. Fires when price >= target_price.
    Returns the short sequential ID scoped to this user.
    """
    existing = list(autosell_col.find({"user_id": user_id}, {"seq": 1}))
    used_seqs = [a.get("seq", 0) for a in existing]
    seq = 1
    while seq in used_seqs:
        seq += 1
    autosell_col.insert_one({
        "user_id": user_id,
        "seq": seq,
        "symbol": symbol,
        "quantity": quantity,
        "target_price": target_price,
        "created_at": time.time(),
    })
    return seq


def get_user_autosells(user_id: str) -> list:
    orders = list(autosell_col.find({"user_id": user_id}))
    return sorted(orders, key=lambda a: a["seq"])


def remove_autosell_by_seq(user_id: str, seq: int) -> dict | None:
    """Delete auto-sell order by short ID. Returns the doc if found, else None."""
    order = autosell_col.find_one({"user_id": user_id, "seq": seq})
    if order:
        autosell_col.delete_one({"_id": order["_id"]})
    return order


async def check_autosells(bot):
    """
    Called after every stock price update.
    Executes pending auto-sell orders whose target price has been reached,
    credits the user's wallet, and sends a DM confirmation.
    """
    from utils.economy import update_wallet, get_wallet, get_bank, get_prestige_level

    orders = list(autosell_col.find())
    for order in orders:
        symbol = order["symbol"]
        if symbol not in STOCKS:
            continue
        try:
            current_price = get_current_price(symbol)
        except Exception:
            continue

        if current_price < order["target_price"]:
            continue

        # Price has reached the target — execute the sell
        user_id = order["user_id"]
        quantity = order["quantity"]

        portfolio = get_user_portfolio(user_id)
        owned = portfolio.get(symbol, {}).get("quantity", 0)
        avg_price = portfolio.get(symbol, {}).get("avg_price", 0)

        sell_qty = min(quantity, owned)
        if sell_qty <= 0:
            # User no longer holds shares — remove the stale order silently
            autosell_col.delete_one({"_id": order["_id"]})
            continue

        # Apply same fee logic as manual sells
        wallet = get_wallet(user_id)
        bank = get_bank(user_id)
        level = get_prestige_level(wallet + bank)
        fee_multiplier = max(0, 1 - (level * 0.15))
        current_fee = STOCK_FEE * fee_multiplier

        total_gain = int(current_price * sell_qty * (1 - current_fee))
        profit = int((current_price - avg_price) * sell_qty)
        fee_paid = int(current_price * sell_qty * current_fee)

        sold = sell_stock(user_id, symbol, sell_qty)
        if sold:
            update_wallet(user_id, total_gain)

            try:
                user = await bot.fetch_user(int(user_id))

                if profit > 0:
                    result_line = f"📈 **+🪙 {profit:,}** profit"
                    color = 0x2ECC71
                    title = "✅ Auto-sell executed — Profit"
                elif profit < 0:
                    result_line = f"📉 **-🪙 {abs(profit):,}** loss"
                    color = 0xE74C3C
                    title = "✅ Auto-sell executed — Loss"
                else:
                    result_line = "➡️ Break even"
                    color = 0x95A5A6
                    title = "✅ Auto-sell executed"

                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="📦 Shares sold", value=f"**{sell_qty}x {symbol}**", inline=True)
                embed.add_field(name="💰 Received", value=f"🪙 {total_gain:,}", inline=True)
                embed.add_field(
                    name="📊 Sale vs avg buy price",
                    value=f"🪙 {current_price:,} → avg 🪙 {int(avg_price):,}",
                    inline=False,
                )
                embed.add_field(name="📈 Result", value=result_line, inline=False)
                footer = f"Target: 🪙 {order['target_price']:,}"
                if fee_paid > 0:
                    footer += f" • Fee applied: 🪙 {fee_paid:,}"
                embed.set_footer(text=footer)
                await user.send(embed=embed)
            except Exception:
                pass  # DMs closed or user not found

            # Only remove the order after a confirmed successful sell
            autosell_col.delete_one({"_id": order["_id"]})
