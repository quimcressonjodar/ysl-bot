import time
import platform
import discord
from discord import app_commands
from discord.ext import commands

from database import tutorial_col


# ---------------------------------------------------------------------------
# Tutorial step definitions
# Each step:
#   watch    — command name the bot waits for (exact match, no prefix)
#   embed_fn — function() -> discord.Embed sent as the "do this now" prompt
# ---------------------------------------------------------------------------

def _e(title: str, desc: str, color: int, fields: list[tuple]) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color)
    for name, value in fields:
        e.add_field(name=name, value=value, inline=False)
    return e


STEPS: list[dict] = [
    # ── Step 0 ──────────────────────────────────────────────────────────────
    {
        "watch": "daily",
        "embed": lambda: _e(
            "📅 Step 1 — Claim your daily coins",
            (
                "Every day you can claim free coins just for showing up.\n\n"
                "Go to the server and type:"
            ),
            0x2ECC71,
            [
                ("Command", "`!daily`"),
                ("What it does", "Gives you ~1,000 🪙 once every 24 hours. Never skip it."),
                ("⏳ Waiting…", "I'll detect it automatically and continue when you've done it!"),
            ],
        ),
    },
    # ── Step 1 ──────────────────────────────────────────────────────────────
    {
        "watch": "balance",
        "embed": lambda: _e(
            "💰 Step 2 — Check your balance",
            "Nice! You've got coins. Let's see them.",
            0xF1C40F,
            [
                ("Command", "`!balance`"),
                ("What it does", "Shows your wallet, bank, total net worth and prestige level."),
                ("💡 Tip", "Wallet = coins you carry (can be robbed). Bank = safe storage."),
                ("⏳ Waiting…", "Go ahead — type `!balance` in the server!"),
            ],
        ),
    },
    # ── Step 2 ──────────────────────────────────────────────────────────────
    {
        "watch": "work",
        "embed": lambda: _e(
            "🔨 Step 3 — Go to work",
            "You can earn extra coins by working. It has a cooldown, but it's 100% safe — no risk.",
            0xE67E22,
            [
                ("Command", "`!work`"),
                ("What it does", "Picks a random job and pays you coins. Safe, consistent income."),
                ("⏳ Waiting…", "Type `!work` in the server!"),
            ],
        ),
    },
    # ── Step 3 ──────────────────────────────────────────────────────────────
    {
        "watch": "deposit",
        "embed": lambda: _e(
            "🏦 Step 4 — Deposit your coins",
            (
                "Your wallet is exposed — anyone can rob you if you're WANTED. "
                "The bank is safe. Let's move your coins there."
            ),
            0x3498DB,
            [
                ("Command", "`!deposit all`"),
                ("What it does", "Moves everything from your wallet into the bank."),
                ("💡 Always do this", "After every `!work`, `!daily`, or big win — deposit immediately."),
                ("⏳ Waiting…", "Type `!deposit all` in the server!"),
            ],
        ),
    },
    # ── Step 4 ──────────────────────────────────────────────────────────────
    {
        "watch": "bounties",
        "embed": lambda: _e(
            "🎯 Step 5 — Check your bounty contracts",
            (
                "Bounties are long-term challenges that reward you for playing naturally. "
                "You probably already made progress on some just now."
            ),
            0xE74C3C,
            [
                ("Command", "`!bounties`"),
                ("What it does", (
                    "Shows all active contracts and your personal progress.\n"
                    "Examples: *work 10 times*, *catch a criminal*, *win at casino*."
                )),
                ("⚙️ Auto-tracked", "Progress is counted automatically — just play normally."),
                ("⏳ Waiting…", "Type `!bounties` in the server!"),
            ],
        ),
    },
    # ── Step 5 ──────────────────────────────────────────────────────────────
    {
        "watch": "stocks",
        "embed": lambda: _e(
            "📈 Step 6 — Look at the stock market",
            (
                "Once you have spare coins, the stock market is one of the best ways "
                "to grow them. Prices update every few minutes and you earn dividends daily."
            ),
            0x1ABC9C,
            [
                ("Command", "`!stocks`"),
                ("What it does", "Lists all companies, their current price and daily % change."),
                ("🛒 To buy", "`!sbuy <SYMBOL> <amount>` — e.g. `!sbuy PROTOX 10`"),
                ("💼 Your holdings", "`!portfolio` — see your positions and total profit/loss."),
                ("⏳ Waiting…", "Type `!stocks` in the server to take a look!"),
            ],
        ),
    },
]

FINAL_EMBED = _e(
    "🎉 Tutorial Complete!",
    (
        "You know the basics now. Here's a quick cheat-sheet of everything else:"
    ),
    0xF1C40F,
    [
        ("💸 More income", "`!weekly` (once/week) • `!claim` (hourly, if you own roles)"),
        ("🎰 Casino", "`!blackjack <bet>` • `!roulette <bet> <choice>` • `!dice <bet>`"),
        ("🚨 Crime", "`!crime` • `!rob @user` — risky but pays more. Going WANTED = others can `!catch` you."),
        ("🐾 Pets", "`!shop` → `!buy <pet>` → `!feed` → `!battle @user` → `!adventures <pet>`"),
        ("🏦 Loans", "`!loan <amount>` → repay with `!repay <amount>` — interest grows over time!"),
        ("🔔 Price alerts", "`!alert <SYMBOL> <price>` — get a DM when a stock hits your target."),
        ("⭐ Prestige", "Your rank = your total net worth. Higher prestige = lower stock fees."),
        ("📋 All commands", "Type `!help` anytime to reopen this reference."),
    ],
)

# Reference-only embed (shown by !help without tutorial flow)
REFERENCE_EMBED = _e(
    "📖 Economy — Command Guide",
    "Every command explained. Use `!tutorial` for the step-by-step interactive walkthrough.",
    0x2B2D31,
    [
        (
            "💰 Free Income",
            "`!daily` — ~1,000 🪙 every 24 h\n"
            "`!weekly` — ~25,000 🪙 once per week\n"
            "`!claim` — hourly bonus if you own income roles from the shop",
        ),
        (
            "🏦 Balance & Banking",
            "`!balance` — wallet, bank, net worth and prestige level\n"
            "`!deposit <amount|all>` — move coins from wallet → bank (safe from robbers)\n"
            "`!withdraw <amount|all>` — take coins out of the bank\n"
            "`!pay @user <amount>` — send coins directly to someone\n"
            "`!leaderboard` — richest players ranked by net worth",
        ),
        (
            "💼 Work & Crime",
            "`!work` — random job, earns coins on a cooldown. 100% safe.\n"
            "`!crime` — attempt a crime for 2k–6.5k 🪙. Fail → fine + WANTED 🚨\n"
            "`!rob @user` — steal from someone's wallet. Fail → fine + WANTED 🚨\n"
            "`!catch @user` — catch a WANTED player for a reward (15 min cooldown)\n"
            "⚠️ WANTED = anyone can catch you and take a reward from your wallet. Deposit fast!",
        ),
        (
            "🎰 Casino",
            "`!blackjack <bet>` — beat the dealer to 21. Win = 2× your bet\n"
            "`!roulette <bet> <red/black/even/odd/number/1st12/2nd12/3rd12>` — up to 36× payout\n"
            "`!dice <bet>` — roll against the house\n"
            "`!claimdrop` — grab a global coin/item drop before anyone else (admin-triggered)",
        ),
        (
            "🎯 Bounties",
            "`!bounties` — view active contracts and your progress on each\n"
            "Progress is tracked automatically as you play. Examples: *work 10 times*, "
            "*catch a criminal*, *win at blackjack*. Completing a contract pays a big reward.",
        ),
        (
            "🐾 Pets",
            "`!shop` — browse pets, food and roles for sale\n"
            "`!buy <pet>` — purchase a pet (coins from wallet)\n"
            "`!pets` — view all your pets: HP, damage, hunger, status\n"
            "`!feed <pet> <food>` — restore hunger (hungry pets lose stats)\n"
            "`!breed <pet1> <pet2>` — combine two pets into a stronger offspring\n"
            "`!battle @user` — your strongest pet fights theirs. Winner earns coins\n"
            "`!adventures <pet>` — send a pet to find coins, food or rare loot\n"
            "`!sell_pet <pet>` — sell a pet for 50% of its shop price",
        ),
        (
            "📈 Stocks",
            "`!stocks` — all companies: price, daily % change\n"
            "`!stocks <SYMBOL>` — detailed view of one stock\n"
            "`!sbuy <SYMBOL> <amount|all>` — buy shares\n"
            "`!ssell <SYMBOL> <amount|all>` — sell shares\n"
            "`!portfolio` — your holdings, current value, total profit/loss\n"
            "`!alert <SYMBOL> <price>` — DM alert when a stock hits your target\n"
            "`!myalerts` — see your active alerts (shows ID 1, 2, 3…)\n"
            "`!cancelalert <id>` — remove an alert by its short number\n"
            "`!autosell <SYMBOL> <quantity> <target>` — auto-sell shares when price reaches target\n"
            "`!myautosells` — see your pending auto-sell orders\n"
            "`!cancelautosell <id>` — cancel an auto-sell order\n"
            "📅 Dividends paid daily: 0.05%–2% depending on company performance",
        ),
        (
            "🏦 Loans",
            "`!loan <amount>` — borrow coins instantly (interest accrues over time)\n"
            "`!repay <amount>` — pay back part or all of your debt\n"
            "`!debt` — check your outstanding balance and accrued interest\n"
            "⚠️ Debt compounds — only borrow if you have a plan to repay.",
        ),
        (
            "🎒 Inventory & Shop",
            "`!inventory` — items you own: food, loot, resale value\n"
            "`!sell` — sell an item from your inventory for coins",
        ),
        (
            "⭐ Prestige & Stats",
            "`!balance` — shows your prestige level (based on total net worth)\n"
            "Higher prestige = lower stock trading fees (up to −90% at max rank)\n"
            "`!botstats` — bot ping, uptime, server count\n"
            "`!tutorial` — restart the interactive step-by-step walkthrough",
        ),
    ],
)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_tutorial_state(user_id: str) -> dict | None:
    return tutorial_col.find_one({"_id": user_id})


def set_tutorial_step(user_id: str, step: int, guild_id: int | None = None):
    update: dict = {"step": step, "active": True}
    if guild_id is not None:
        update["guild_id"] = guild_id
    tutorial_col.update_one({"_id": user_id}, {"$set": update}, upsert=True)


def finish_tutorial(user_id: str):
    tutorial_col.update_one(
        {"_id": user_id},
        {"$set": {"active": False}},
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    # ── !tutorial ────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="tutorial",
        description="Start the interactive economy tutorial — the bot guides you step by step",
    )
    async def tutorial_command(self, ctx: commands.Context):
        user_id = str(ctx.author.id)

        # Reset / start tutorial (bind to this guild)
        guild_id = ctx.guild.id if ctx.guild else None
        set_tutorial_step(user_id, 0, guild_id=guild_id)

        # Try to DM the user
        try:
            intro = discord.Embed(
                title="🎮 Welcome to the Economy Tutorial!",
                description=(
                    f"Hey **{ctx.author.display_name}**! I'll guide you through the economy "
                    f"step by step.\n\n"
                    "Each step I'll tell you exactly which command to use. "
                    "Once you run it **in the server**, I'll automatically detect it "
                    "and send you the next step here.\n\n"
                    "Let's start! 👇"
                ),
                color=0xF1C40F,
            )
            await ctx.author.send(embed=intro)
            await ctx.author.send(embed=STEPS[0]["embed"]())
        except discord.Forbidden:
            await ctx.send(
                "❌ I can't DM you! Please enable DMs from server members "
                "(User Settings → Privacy & Safety) and try `!tutorial` again.",
                ephemeral=True,
            )
            finish_tutorial(user_id)
            return

        # Acknowledge in channel (ephemeral so it doesn't clutter)
        await ctx.send(
            "📬 Check your DMs! I'll guide you through the tutorial there.",
            ephemeral=True,
        )

    # ── !help (reference only) ───────────────────────────────────────────────

    @commands.hybrid_command(
        name="help",
        description="Quick command reference. Use !tutorial for the interactive walkthrough.",
    )
    async def help_command(self, ctx: commands.Context):
        await ctx.send(embed=REFERENCE_EMBED)

    # ── Command completion listener ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        state = get_tutorial_state(user_id)
        if not state or not state.get("active"):
            return

        step_idx = state.get("step", 0)
        if step_idx >= len(STEPS):
            return

        expected_cmd = STEPS[step_idx]["watch"]
        if ctx.command is None or ctx.command.name != expected_cmd:
            return

        # Guild guard — only advance from the same guild where tutorial started
        bound_guild = state.get("guild_id")
        if bound_guild and (ctx.guild is None or ctx.guild.id != bound_guild):
            return

        next_idx = step_idx + 1

        try:
            if next_idx >= len(STEPS):
                # Tutorial done — mark finished BEFORE sending DMs
                finish_tutorial(user_id)
                done = discord.Embed(
                    title="✅ Great job!",
                    description=f"You completed step {step_idx + 1} — **`!{expected_cmd}`**. That's the last one!",
                    color=0x2ECC71,
                )
                await ctx.author.send(embed=done)
                await ctx.author.send(embed=FINAL_EMBED)
            else:
                # Send DMs first; only persist new step if they succeed
                confirm = discord.Embed(
                    title=f"✅ Step {step_idx + 1} done!",
                    description=f"You used **`!{expected_cmd}`** — nice work! Here's what's next:",
                    color=0x2ECC71,
                )
                await ctx.author.send(embed=confirm)
                await ctx.author.send(embed=STEPS[next_idx]["embed"]())
                # DMs delivered successfully — now persist
                set_tutorial_step(user_id, next_idx)
        except discord.Forbidden:
            # User closed DMs mid-tutorial — deactivate so we stop tracking
            finish_tutorial(user_id)

    # ── !botstats ────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="botstats", description="Show bot performance stats: ping, uptime and more")
    async def botstats(self, ctx: commands.Context):
        before = time.perf_counter()
        msg = await ctx.send("📡 Measuring latency...")
        after = time.perf_counter()
        rest_ping = round((after - before) * 1000)
        ws_ping = round(self.bot.latency * 1000)

        uptime_seconds = int(time.time() - self.start_time)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        total_commands = len([c for c in self.bot.commands if not c.hidden])

        def ping_emoji(ms):
            if ms < 80:
                return "🟢"
            elif ms < 200:
                return "🟡"
            else:
                return "🔴"

        embed = discord.Embed(title="🤖 Bot Stats", color=0x2B2D31)
        embed.add_field(
            name="📡 Latency",
            value=(
                f"{ping_emoji(ws_ping)} **WebSocket:** `{ws_ping} ms`\n"
                f"{ping_emoji(rest_ping)} **REST API:** `{rest_ping} ms`"
            ),
            inline=False,
        )
        embed.add_field(name="⏱️ Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="🏰 Servers", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="👥 Members", value=f"`{total_members:,}`", inline=True)
        embed.add_field(name="⚙️ Commands", value=f"`{total_commands}`", inline=True)
        embed.add_field(name="🐍 Python", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="📦 discord.py", value=f"`{discord.__version__}`", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await msg.edit(content=None, embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
