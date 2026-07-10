import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import random
from config import STOCKS, STOCK_UPDATE_INTERVAL, STOCK_FEE, OWNER_IDS
from utils.stocks import (
    update_stock_prices, generate_stock_chart, get_current_price,
    get_user_portfolio, buy_stock, sell_stock, process_dividends,
    load_ipo_stocks, add_ipo_stock,
    add_price_alert, get_user_alerts, remove_alert_by_seq, check_price_alerts,
    add_autosell, get_user_autosells, remove_autosell_by_seq, check_autosells,
    stock_alerts_col, user_stocks_col,
)
from utils.stock_news import get_random_news
from utils.economy import get_wallet, update_wallet, get_bank, get_prestige_level
from utils.helpers import is_admin

STOCK_NEWS_CHANNEL_ID = 1513755454029959239


class StockView(discord.ui.View):
    def __init__(self, ctx, symbol):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.symbol = symbol
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

    @discord.ui.button(label="Buy 1", style=discord.ButtonStyle.green)
    async def buy_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 1, "buy")

    @discord.ui.button(label="Buy 10", style=discord.ButtonStyle.green)
    async def buy_ten(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 10, "buy")

    @discord.ui.button(label="Sell 1", style=discord.ButtonStyle.red)
    async def sell_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 1, "sell")

    @discord.ui.button(label="Sell All", style=discord.ButtonStyle.red)
    async def sell_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        portfolio = get_user_portfolio(str(interaction.user.id))
        quantity = portfolio.get(self.symbol, {}).get("quantity", 0)
        if quantity <= 0:
            return await interaction.response.send_message("❌ You don't own any shares of this stock.", ephemeral=True)
        await self.process_trade(interaction, quantity, "sell")

    async def process_trade(self, interaction, quantity, side):
        if str(interaction.user.id) != str(self.ctx.author.id):
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
        await self.process_trade_direct(interaction, quantity, side)

    async def process_trade_direct(self, target, quantity, side):
        is_interaction = isinstance(target, discord.Interaction)
        user = target.user if is_interaction else target.author
        user_id = str(user.id)

        price = get_current_price(self.symbol)
        wallet = get_wallet(user_id)
        bank = get_bank(user_id)
        level = get_prestige_level(wallet + bank)

        fee_multiplier = max(0, 1 - (level * 0.15))
        current_fee = STOCK_FEE * fee_multiplier

        if side == "buy":
            total_cost = int(price * quantity * (1 + current_fee))
            if wallet < total_cost:
                msg = f"❌ You need 🪙 {total_cost:,} to buy {quantity} shares (including fees)."
                return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)

            update_wallet(user_id, -total_cost)
            buy_stock(user_id, self.symbol, quantity, price)
            msg = f"✅ Bought {quantity} shares of **{self.symbol}** for 🪙 {total_cost:,}!"
            return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)
        else:
            total_gain = int(price * quantity * (1 - current_fee))
            portfolio = get_user_portfolio(user_id)
            avg_price = portfolio.get(self.symbol, {}).get("avg_price", 0)
            profit = int((price - avg_price) * quantity)

            if sell_stock(user_id, self.symbol, quantity):
                update_wallet(user_id, total_gain)

                if profit > 0:
                    from utils.bounties import track_bounty_progress
                    bot = self.ctx.bot if hasattr(self.ctx, "bot") else self.ctx
                    await track_bounty_progress(bot, user_id, "TRADER", profit)

                if profit > 0:
                    result_line = f"📈 **+🪙 {profit:,}** profit"
                    color = 0x2ECC71
                    title = "✅ Sale completed — Profit"
                elif profit < 0:
                    result_line = f"📉 **-🪙 {abs(profit):,}** loss"
                    color = 0xE74C3C
                    title = "✅ Sale completed — Loss"
                else:
                    result_line = "➡️ Break even (sold at avg cost)"
                    color = 0x95A5A6
                    title = "✅ Sale completed"

                fee_paid = int(price * quantity * current_fee)
                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="📦 Shares sold", value=f"**{quantity}x {self.symbol}**", inline=True)
                embed.add_field(name="💰 Received", value=f"🪙 {total_gain:,}", inline=True)
                embed.add_field(
                    name="📊 Sale vs avg buy price",
                    value=f"🪙 {price:,} → avg 🪙 {int(avg_price):,}",
                    inline=False,
                )
                embed.add_field(name="📈 Result", value=result_line, inline=False)
                if fee_paid > 0:
                    embed.set_footer(text=f"Fee applied: 🪙 {fee_paid:,}")

                return await target.response.send_message(embed=embed, ephemeral=True) if is_interaction else await target.send(embed=embed)
            else:
                msg = "❌ You don't have enough shares to sell."
                return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)


class Stocks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_stocks.start()
        self.distribute_dividends.start()

    def cog_unload(self):
        self.update_stocks.cancel()
        self.distribute_dividends.cancel()

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

    @tasks.loop(minutes=STOCK_UPDATE_INTERVAL)
    async def update_stocks(self):
        try:
            news_impact = {}
            if random.random() < 0.50:
                symbol, message, multiplier = get_random_news()
                news_impact[symbol] = multiplier

                channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(title="🗞️ Market News Alert", description=message, color=0xF1C40F)
                    if symbol != "ALL":
                        embed.set_footer(text=f"Impact: {symbol}")
                    await channel.send(embed=embed)

            update_stock_prices(news_impact)

            # Check price alerts and auto-sell orders after every price update
            await check_price_alerts(self.bot)
            await check_autosells(self.bot)

        except Exception as e:
            print(f"STOCK UPDATE ERROR: {e}")

    @tasks.loop(hours=24)
    async def distribute_dividends(self):
        try:
            users, total, rates = process_dividends()
            if users > 0:
                channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
                if channel:
                    # Sort stocks by dividend rate to show best and worst payers
                    sorted_rates = sorted(
                        rates.items(), key=lambda x: x[1]["rate"], reverse=True
                    )
                    top = sorted_rates[:3]
                    bottom = sorted_rates[-3:]

                    def fmt(symbol, info):
                        perf = info["performance"]
                        arrow = "📈" if perf >= 0 else "📉"
                        sign = "+" if perf >= 0 else ""
                        return f"**{symbol}** {arrow} {sign}{perf:.1%} → {info['rate']:.2%} rate"

                    top_lines = "\n".join(fmt(s, i) for s, i in top)
                    bottom_lines = "\n".join(fmt(s, i) for s, i in bottom)

                    embed = discord.Embed(
                        title="💰 Daily Dividends Distributed",
                        description=f"🪙 **{total:,}** coins paid out to **{users}** shareholders!",
                        color=0x2ECC71,
                    )
                    embed.add_field(name="🏆 Top payers", value=top_lines, inline=False)
                    embed.add_field(name="📉 Lowest payers", value=bottom_lines, inline=False)
                    embed.set_footer(text="Dividend rate = 0.3% base ± 24h performance. Range: 0.05% – 2%")
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"DIVIDEND ERROR: {e}")

    @distribute_dividends.before_loop
    async def before_distribute_dividends(self):
        await self.bot.wait_until_ready()

    @update_stocks.before_loop
    async def before_update_stocks(self):
        await self.bot.wait_until_ready()
        # Load any persisted IPO stocks into the live STOCKS dict
        load_ipo_stocks()
        # Ensure every stock has at least 2 data points so charts render.
        # We seed each stock individually rather than calling update_stock_prices()
        # once (which only adds 1 point and breaks on the first stock found).
        from utils.stocks import stocks_col
        import time as _time
        needs_seed = []
        for symbol in STOCKS:
            history = stocks_col.find_one({"symbol": symbol})
            if not history or len(history.get("prices", [])) < 2:
                needs_seed.append(symbol)

        for symbol in needs_seed:
            initial_price = STOCKS[symbol].get("initial_price", 500)
            history = stocks_col.find_one({"symbol": symbol})
            existing = history.get("prices", []) if history else []
            # Build a list with at least 2 points
            if len(existing) == 0:
                seed = [
                    {"price": initial_price, "timestamp": _time.time() - 120},
                    {"price": initial_price, "timestamp": _time.time() - 60},
                ]
            else:
                # Has exactly 1 point — add a second one right before it
                seed = [
                    {"price": existing[0]["price"], "timestamp": existing[0]["timestamp"] - 60},
                ] + existing
            if history:
                stocks_col.update_one({"symbol": symbol}, {"$set": {"prices": seed}})
            else:
                stocks_col.insert_one({"symbol": symbol, "prices": seed})

        # Run one full price update so all stocks get a fresh tick
        if needs_seed:
            update_stock_prices()

    # ------------------------------------------------------------------
    # Trading commands
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="sbuy", description="Buy stocks from the market")
    @app_commands.describe(symbol="Stock symbol (e.g. VRTX)", quantity="Amount to buy ('all', 'max', or number)")
    async def sbuy(self, ctx: commands.Context, symbol: str, quantity: str):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)

        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        price = get_current_price(symbol)

        level = get_prestige_level(wallet + get_bank(user_id))
        fee_multiplier = 1.0 + (STOCK_FEE * (1 - (level / 7.0)))
        cost_per_share = price * fee_multiplier

        if quantity.lower() in ["all", "max"]:
            if cost_per_share > wallet:
                return await ctx.send(
                    f"❌ You can't afford any shares of {symbol}. You need at least 🪙 {int(cost_per_share):,}.",
                    ephemeral=True,
                )
            parsed_quantity = int(wallet // cost_per_share)
        else:
            try:
                parsed_quantity = int(quantity.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Invalid quantity. Use a number or 'all'.", ephemeral=True)

        if parsed_quantity <= 0:
            return await ctx.send("❌ Quantity must be positive.", ephemeral=True)

        view = StockView(ctx, symbol)
        await view.process_trade_direct(ctx, parsed_quantity, "buy")

    @commands.hybrid_command(name="ssell", description="Sell stocks to the market")
    @app_commands.describe(symbol="Stock symbol (e.g. VRTX)", quantity="Amount to sell ('all', 'max', or number)")
    async def ssell(self, ctx: commands.Context, symbol: str, quantity: str):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)

        user_id = str(ctx.author.id)
        portfolio = get_user_portfolio(user_id)
        user_shares = portfolio.get(symbol, {}).get("quantity", 0)

        if quantity.lower() in ["all", "max"]:
            parsed_quantity = user_shares
        else:
            try:
                parsed_quantity = int(quantity.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Invalid quantity. Use a number or 'all'.", ephemeral=True)

        if parsed_quantity <= 0:
            return await ctx.send("❌ Quantity must be positive.", ephemeral=True)

        if parsed_quantity > user_shares:
            return await ctx.send(f"❌ You only have {user_shares} shares of {symbol}.", ephemeral=True)

        view = StockView(ctx, symbol)
        await view.process_trade_direct(ctx, parsed_quantity, "sell")

    @commands.hybrid_command(name="stocks", aliases=["socks", "stock", "st"], description="View the stock market")
    async def stocks(self, ctx: commands.Context, symbol: str = None):
        await ctx.defer()

        if not symbol:
            embed = discord.Embed(title="📈 Global Stock Market", color=0x2B2D31)
            description = "Use `!stocks <symbol>` to see detailed charts and trade.\n\n"
            for s, cfg in STOCKS.items():
                try:
                    price = get_current_price(s)
                    description += f"**{s}** - {cfg['name']}\nPrice: 🪙 {price:,}\n\n"
                except Exception:
                    description += f"**{s}** - {cfg['name']}\nPrice: *Calculating...*\n\n"
            embed.description = description
            return await ctx.send(embed=embed)

        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)

        try:
            price = get_current_price(symbol)
            embed = discord.Embed(
                title=f"📊 {STOCKS[symbol]['name']} ({symbol})",
                description=f"{STOCKS[symbol]['description']}\n\n**Current Price:** 🪙 {price:,}",
                color=0x3498DB,
            )

            chart = None
            try:
                chart = generate_stock_chart(symbol)
            except Exception as chart_err:
                print(f"CHART GENERATION ERROR for {symbol}: {chart_err}")

            if chart:
                embed.set_image(url=f"attachment://{symbol}_chart.png")
                view = StockView(ctx, symbol)
                view.message = await ctx.send(embed=embed, file=chart, view=view)
            else:
                view = StockView(ctx, symbol)
                view.message = await ctx.send(embed=embed, view=view)
        except Exception as e:
            print(f"STOCKS COMMAND ERROR: {e}")
            await ctx.send(f"❌ An error occurred while fetching data for {symbol}. Please try again later.")

    @commands.hybrid_command(name="portfolio", aliases=["pfol"], description="View your stock portfolio")
    async def portfolio(self, ctx: commands.Context):
        await ctx.defer()
        try:
            user_id = str(ctx.author.id)
            stocks_data = get_user_portfolio(user_id)

            if not stocks_data:
                return await ctx.send("💼 Your portfolio is empty. Start trading with `!stocks`!")

            embed = discord.Embed(title=f"💼 {ctx.author.display_name}'s Portfolio", color=0x2ECC71)
            total_value = 0
            total_profit = 0

            for symbol, data in stocks_data.items():
                try:
                    current_price = get_current_price(symbol)
                    qty = data["quantity"]
                    avg = data["avg_price"]
                    value = qty * current_price
                    profit = (current_price - avg) * qty
                    total_value += value
                    total_profit += profit
                    p_text = f"+🪙 {profit:,.0f}" if profit >= 0 else f"-🪙 {abs(profit):,.0f}"
                    embed.add_field(
                        name=f"{symbol} ({qty} shares)",
                        value=f"Value: 🪙 {value:,}\nProfit: **{p_text}**\nAvg Cost: 🪙 {avg:,.0f}",
                        inline=True,
                    )
                except Exception as e:
                    print(f"ERROR processing stock {symbol} in portfolio: {e}")
                    continue

            embed.description = (
                f"**Total Portfolio Value:** 🪙 {total_value:,}\n"
                f"**Total Profit/Loss:** 🪙 {total_profit:,.0f}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"PORTFOLIO COMMAND ERROR: {e}")
            await ctx.send("❌ An error occurred while fetching your portfolio. Please try again later.")

    # ------------------------------------------------------------------
    # Price Alert commands
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="alert", description="Set a price alert — get a DM when a stock hits your target")
    @app_commands.describe(symbol="Stock symbol (e.g. CRPT)", price="Target price in coins")
    async def alert(self, ctx: commands.Context, symbol: str, price: int):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(
                f"❌ Stock **{symbol}** not found. Check `!stocks` for available symbols.", ephemeral=True
            )
        if price <= 0:
            return await ctx.send("❌ Target price must be greater than 0.", ephemeral=True)

        current_price = get_current_price(symbol)
        if current_price == price:
            return await ctx.send(
                "❌ Target price equals the current price. Choose a different value.", ephemeral=True
            )

        user_id = str(ctx.author.id)
        existing = get_user_alerts(user_id)
        if len(existing) >= 5:
            return await ctx.send(
                "❌ You already have 5 active alerts (max). Cancel one with `!cancelalert` before adding another.",
                ephemeral=True,
            )

        direction = "above" if price > current_price else "below"
        alert_id = add_price_alert(user_id, symbol, price)

        arrow = "📈" if direction == "above" else "📉"
        verb = "rises to" if direction == "above" else "drops to"

        embed = discord.Embed(
            title="🔔 Price alert set",
            description=(
                f"{arrow} I'll DM you when **{symbol}** {verb} 🪙 **{price:,}**\n\n"
                f"💹 Current price: 🪙 **{current_price:,}**"
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=f"ID: {alert_id} • Cancel with: !cancelalert {alert_id}")
        await ctx.send(embed=embed)


    @commands.hybrid_command(name="myalerts", description="View your active price alerts")
    async def myalerts(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        alerts = get_user_alerts(user_id)

        if not alerts:
            return await ctx.send(
                "📭 You have no active alerts. Create one with `!alert <symbol> <price>`."
            )

        embed = discord.Embed(title="🔔 Your active price alerts", color=0x3498DB)
        for a in alerts:
            symbol = a["symbol"]
            target = a["target_price"]
            direction = a["direction"]
            arrow = "📈" if direction == "above" else "📉"
            verb = "≥" if direction == "above" else "≤"
            try:
                current = get_current_price(symbol)
                current_text = f"Current price: 🪙 {current:,}"
            except Exception:
                current_text = "Current price: unknown"
            embed.add_field(
                name=f"{arrow} {symbol} {verb} 🪙 {target:,}",
                value=f"{current_text}\n`!cancelalert {a['seq']}`",
                inline=False,
            )

        embed.set_footer(text="Use !cancelalert <id> to remove an alert")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="cancelalert", description="Cancel an active price alert")
    @app_commands.describe(alert_id="Alert number shown in !myalerts (e.g. 1, 2, 3)")
    async def cancelalert(self, ctx: commands.Context, alert_id: str):
        user_id = str(ctx.author.id)
        try:
            seq = int(alert_id)
        except ValueError:
            return await ctx.send("❌ Invalid ID — use the number shown in `!myalerts` (e.g. `!cancelalert 1`).", ephemeral=True)

        alert = remove_alert_by_seq(user_id, seq)
        if not alert:
            return await ctx.send("❌ Alert not found. Check your IDs with `!myalerts`.", ephemeral=True)

        embed = discord.Embed(
            title="✅ Alert cancelled",
            description=f"The alert for **{alert['symbol']}** at 🪙 {alert['target_price']:,} has been removed.",
            color=0x2ECC71,
        )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # Auto-sell commands
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="autosell", description="Set an automatic sell order when a stock hits your target price")
    @app_commands.describe(
        symbol="Stock symbol (e.g. VRTX)",
        quantity="Shares to sell: a number, 'all', or 'half'",
        target_price="Price (in coins) at which to trigger the sell",
    )
    async def autosell(self, ctx: commands.Context, symbol: str, quantity: str, target_price: int):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)
        if target_price <= 0:
            return await ctx.send("❌ Target price must be greater than 0.", ephemeral=True)

        user_id = str(ctx.author.id)
        portfolio = get_user_portfolio(user_id)
        owned = portfolio.get(symbol, {}).get("quantity", 0)
        if owned <= 0:
            return await ctx.send(f"❌ You don't own any shares of **{symbol}**.", ephemeral=True)

        q_lower = quantity.lower().strip()
        if q_lower in ("all", "max"):
            parsed_quantity = owned
        elif q_lower == "half":
            parsed_quantity = max(1, owned // 2)
        else:
            try:
                parsed_quantity = int(quantity.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Invalid quantity. Use a number, **all**, or **half**.", ephemeral=True)

        if parsed_quantity <= 0:
            return await ctx.send("❌ Quantity must be greater than 0.", ephemeral=True)
        if parsed_quantity > owned:
            return await ctx.send(
                f"❌ You only own **{owned}** shares of {symbol}, but tried to schedule a sell of **{parsed_quantity}**.",
                ephemeral=True,
            )

        current_price = get_current_price(symbol)
        if target_price <= current_price:
            return await ctx.send(
                f"❌ Target price 🪙 {target_price:,} must be **above** the current price of 🪙 {current_price:,}.\n"
                f"Use `!ssell` to sell immediately at the market price.",
                ephemeral=True,
            )

        existing = get_user_autosells(user_id)
        if len(existing) >= 5:
            return await ctx.send(
                "❌ You already have 5 active auto-sell orders (max). Cancel one with `!cancelautosell` first.",
                ephemeral=True,
            )

        order_id = add_autosell(user_id, symbol, parsed_quantity, target_price)

        embed = discord.Embed(
            title="📤 Auto-sell order set",
            description=(
                f"📈 I'll automatically sell **{parsed_quantity}x {symbol}** when the price reaches 🪙 **{target_price:,}**\n\n"
                f"💹 Current price: 🪙 **{current_price:,}**\n"
                f"🎯 Target price: 🪙 **{target_price:,}** (+{((target_price - current_price) / current_price * 100):.1f}%)"
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=f"ID: {order_id} • Cancel with: !cancelautosell {order_id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="myautosells", description="View your active auto-sell orders")
    async def myautosells(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        orders = get_user_autosells(user_id)

        if not orders:
            return await ctx.send(
                "📭 You have no active auto-sell orders. Create one with `!autosell <symbol> <quantity> <target_price>`."
            )

        embed = discord.Embed(title="📤 Your active auto-sell orders", color=0x3498DB)
        for o in orders:
            symbol = o["symbol"]
            try:
                current = get_current_price(symbol)
                pct = ((o["target_price"] - current) / current) * 100
                current_text = f"Current: 🪙 {current:,} ({pct:+.1f}% to target)"
            except Exception:
                current_text = "Current price: unknown"
            embed.add_field(
                name=f"📈 {symbol} — {o['quantity']} shares @ 🪙 {o['target_price']:,}",
                value=f"{current_text}\n`!cancelautosell {o['seq']}`",
                inline=False,
            )

        embed.set_footer(text="Use !cancelautosell <id> to remove an order")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="cancelautosell", description="Cancel an active auto-sell order")
    @app_commands.describe(order_id="Order number shown in !myautosells (e.g. 1, 2, 3)")
    async def cancelautosell(self, ctx: commands.Context, order_id: str):
        user_id = str(ctx.author.id)
        try:
            seq = int(order_id)
        except ValueError:
            return await ctx.send(
                "❌ Invalid ID — use the number shown in `!myautosells` (e.g. `!cancelautosell 1`).", ephemeral=True
            )

        order = remove_autosell_by_seq(user_id, seq)
        if not order:
            return await ctx.send("❌ Order not found. Check your IDs with `!myautosells`.", ephemeral=True)

        embed = discord.Embed(
            title="✅ Auto-sell order cancelled",
            description=(
                f"The auto-sell order for **{order['quantity']}x {order['symbol']}** "
                f"at 🪙 {order['target_price']:,} has been removed."
            ),
            color=0x2ECC71,
        )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # IPO command (admin only — fully automatic)
    # ------------------------------------------------------------------

    # Pool of candidate companies for automatic IPOs.
    # The bot picks one at random that isn't already listed.
    IPO_POOL = {
        "NOVA": {"name": "Nova Systems",          "sector": "Technology",      "volatility": 0.12, "initial_price": 480,  "description": "Next-gen microchip and neural interface hardware."},
        "QNTM": {"name": "Quantum Leap Computing","sector": "Technology",      "volatility": 0.18, "initial_price": 620,  "description": "Pioneer in stable quantum computing and encryption."},
        "NXUS": {"name": "Nexus Networks",        "sector": "Telecom",         "volatility": 0.11, "initial_price": 450,  "description": "Global 7G infrastructure and satellite internet provider."},
        "ZRTH": {"name": "Zeroth AI",             "sector": "AI",              "volatility": 0.16, "initial_price": 550,  "description": "Cutting-edge large language models and autonomous systems."},
        "SOLX": {"name": "SolarX",                "sector": "Energy",          "volatility": 0.13, "initial_price": 390,  "description": "Record-efficiency solar panels and floating solar farms."},
        "HYDR": {"name": "HydroGen Power",        "sector": "Energy",          "volatility": 0.14, "initial_price": 420,  "description": "Green hydrogen production and freight supply chains."},
        "CARB": {"name": "CarbonZero",            "sector": "Environment",     "volatility": 0.12, "initial_price": 360,  "description": "Direct-air carbon capture and global credit trading."},
        "BRVK": {"name": "BraveBank",             "sector": "Finance",         "volatility": 0.14, "initial_price": 500,  "description": "Zero-fee digital bank with AI financial advisors."},
        "PYDE": {"name": "PyDex Exchange",        "sector": "Crypto/DeFi",     "volatility": 0.20, "initial_price": 340,  "description": "Regulated decentralised exchange and CBDC pilot partner."},
        "GNTX": {"name": "Genetix Corp",          "sector": "Biotech",         "volatility": 0.17, "initial_price": 580,  "description": "CRISPR gene therapy and genome sequencing at scale."},
        "MNDR": {"name": "MindRise",              "sector": "Neurotech",       "volatility": 0.19, "initial_price": 610,  "description": "Non-invasive brain implants and neuro-enhancement tech."},
        "DRFT": {"name": "Drift Motors",          "sector": "Automotive",      "volatility": 0.13, "initial_price": 470,  "description": "High-performance electric vehicles and autonomous driving."},
        "SKYW": {"name": "SkyWay Airlines",       "sector": "Aviation",        "volatility": 0.11, "initial_price": 410,  "description": "Global airline pioneering hydrogen-powered aircraft."},
        "XPRS": {"name": "Xpress Logistics",      "sector": "Logistics",       "volatility": 0.10, "initial_price": 380,  "description": "Autonomous drone delivery and robotic warehouse networks."},
        "VRTL": {"name": "VirtualWorld",          "sector": "Gaming/Metaverse","volatility": 0.15, "initial_price": 520,  "description": "Immersive VR metaverse and top-tier esports publisher."},
        "PLSR": {"name": "Pulsar Entertainment", "sector": "Entertainment",    "volatility": 0.12, "initial_price": 460,  "description": "Box-office studio, streaming platform and music label."},
        "NUTX": {"name": "NutriX",               "sector": "Food & Consumer",  "volatility": 0.10, "initial_price": 350,  "description": "Lab-grown meat and personalised nutrition subscriptions."},
        "ARMX": {"name": "ArmX Defense",         "sector": "Defense",          "volatility": 0.14, "initial_price": 540,  "description": "Autonomous combat drones and NATO cyber warfare systems."},
        "BRKR": {"name": "BrickRock Properties", "sector": "Real Estate",      "volatility": 0.09, "initial_price": 430,  "description": "Luxury developments and smart-home residential communities."},
    }

    @commands.hybrid_command(
        name="ipo",
        description="Randomly list a new company on the market, removing the worst performer (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def ipo(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("❌ Admin only.", ephemeral=True)

        # Pick a random candidate not already listed
        available = [s for s in self.IPO_POOL if s not in STOCKS]
        if not available:
            return await ctx.send(
                "❌ All IPO candidates are already listed on the market.", ephemeral=True
            )

        symbol = random.choice(available)
        data = self.IPO_POOL[symbol]

        # ── Pre-compute which stock will be delisted and its last price ──────
        worst_symbol = None
        worst_performance = float("inf")
        for s in list(STOCKS.keys()):
            try:
                price = get_current_price(s)
            except Exception:
                price = STOCKS[s]["initial_price"]
            initial = STOCKS[s].get("initial_price", 500)
            performance = (price - initial) / initial if initial else 0
            if performance < worst_performance:
                worst_performance = performance
                worst_symbol = s

        # Grab last price and all holders BEFORE the stock is removed
        delisted_price = 0
        holders = []  # list of (user_id, quantity)
        if worst_symbol:
            try:
                delisted_price = get_current_price(worst_symbol)
            except Exception:
                delisted_price = STOCKS[worst_symbol].get("initial_price", 0)

            for doc in user_stocks_col.find({f"stocks.{worst_symbol}": {"$exists": True}}):
                qty = doc.get("stocks", {}).get(worst_symbol, {}).get("quantity", 0)
                if qty > 0:
                    holders.append((doc["_id"], qty))

        # ── Execute the IPO / delisting ───────────────────────────────────────
        removed = add_ipo_stock(symbol, data)

        # ── Pay out and clean up delisted holders ─────────────────────────────
        paid_out = 0
        if removed and holders:
            from utils.economy import update_wallet
            for user_id, qty in holders:
                payout = delisted_price * qty
                if payout > 0:
                    update_wallet(user_id, payout)
                    paid_out += 1
                # Remove the delisted stock from the user's portfolio
                user_stocks_col.update_one(
                    {"_id": user_id},
                    {"$unset": {f"stocks.{removed}": ""}},
                )
                # DM the user
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    dm_embed = discord.Embed(
                        title="📉 Your stock has been delisted",
                        description=(
                            f"**{removed}** was the worst-performing company on the market "
                            f"and has been removed following a new IPO.\n\n"
                            f"Your **{qty}** share(s) have been automatically liquidated "
                            f"at the last known price of 🪙 **{delisted_price:,}** per share.\n\n"
                            f"💰 You received: 🪙 **{delisted_price * qty:,}**"
                        ),
                        color=0xE74C3C,
                    )
                    dm_embed.set_footer(text="Funds have been added to your wallet.")
                    await user.send(embed=dm_embed)
                except Exception:
                    pass  # DMs closed or user not found

        # ── Also cancel any alerts / autosells for the delisted stock ─────────
        if removed:
            stock_alerts_col.delete_many({"symbol": removed})
            from utils.stocks import autosell_col
            autosell_col.delete_many({"symbol": removed})

        # ── Announce ──────────────────────────────────────────────────────────
        embed = discord.Embed(title="🏦 New company listed on the market!", color=0xF1C40F)
        embed.add_field(name="🆕 New listing", value=f"**{symbol}** — {data['name']}", inline=False)
        embed.add_field(name="🏭 Sector", value=data["sector"], inline=True)
        embed.add_field(name="💹 Starting price", value=f"🪙 {data['initial_price']:,}", inline=True)
        embed.add_field(name="📊 Volatility", value=f"{data['volatility']:.0%}", inline=True)
        embed.add_field(name="📝 About", value=data["description"], inline=False)
        if removed:
            holder_note = f"\n👥 {paid_out} holder(s) were automatically paid out and notified." if holders else ""
            embed.add_field(
                name="📉 Delisted (worst performer)",
                value=f"**{removed}** has been removed from the market.{holder_note}",
                inline=False,
            )
        embed.set_footer(text="Market news can already affect this company.")

        channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
        if channel and channel.id != ctx.channel.id:
            await channel.send(embed=embed)

        await ctx.send(embed=embed)


    # ── !raise ────────────────────────────────────────────────────────────────

    @commands.command(name="raise", hidden=True)
    async def stock_raise(self, ctx: commands.Context, symbol: str, amount: int):
        """Owner-only: manually spike a stock's price by <amount>."""
        if ctx.author.id not in OWNER_IDS:
            return

        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Unknown stock `{symbol}`.", delete_after=5)

        from utils.stocks import stocks_col
        history = stocks_col.find_one({"symbol": symbol})
        if not history or not history.get("prices"):
            return await ctx.send(f"❌ No price history for `{symbol}`.", delete_after=5)

        current = history["prices"][-1]["price"]
        new_price = max(50, current + amount)
        new_entry = {"price": new_price, "timestamp": time.time()}

        prices = history["prices"] + [new_entry]
        stocks_col.update_one({"symbol": symbol}, {"$set": {"prices": prices}})

        direction = "📈" if amount >= 0 else "📉"
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass
        await ctx.send(
            f"{direction} **{symbol}** {current:,} → **{new_price:,}** ({'+' if amount >= 0 else ''}{amount:,})",
            delete_after=10,
        )

        # Trigger autosell check immediately so orders fire on manual spikes too
        try:
            await check_autosells(self.bot)
        except Exception as e:
            print(f"[raise] check_autosells error: {e}")


async def setup(bot):
    await bot.add_cog(Stocks(bot))
