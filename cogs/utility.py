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
        ("🎰 Casino & Games", "`!blackjack <bet>` • `!roulette <bet> <choice>` • `!dice <bet>` • `!guess <bet>` • `!bjpvp @user <bet>` • `!horserace`"),
        ("🚨 Crime", "`!crime` • `!rob @user` — risky but pays more. Going WANTED = others can `!catch` you."),
        ("🐾 Pets", "`!shop` → `!buy <pet>` → `!feed` → `!battle @user` → `!adventures <pet>`"),
        ("🏦 Loans", "`!loan <amount>` → repay with `!repay <amount>` — interest grows over time!"),
        ("🔔 Price alerts", "`!alert <SYMBOL> <price>` — get a DM when a stock hits your target."),
        ("📊 Leveling", "`!rank` — your XP card • `!lvltop` — XP leaderboard • `!msgtop` — message leaderboard"),
        ("🎉 Giveaways & Polls", "`!gstart` • `!gend` • `!greroll` • `!glist` • `!poll` • `!quickpoll`"),
        ("💞 Fun", "`!love @user` • `!kiss @user` • `!8ball <question>`"),
        ("💤 AFK & Reminders", "`!afk [reason]` — go AFK • `!remindme <time> <text>` — set a reminder"),
        ("🏢 Business", "`!business shop` → `!business buy <type>` → `!business collect`"),
        ("⭐ Prestige", "Your rank = your total net worth. Higher prestige = lower stock fees."),
        ("📋 All commands", "Type `!help` anytime for the full reference."),
    ],
)

# ── Interactive help menu ────────────────────────────────────────────────────
#
# Keep this catalog explicit instead of reading bot.commands at runtime.  That
# lets the help menu group nested commands intentionally and keeps private
# implementation commands out of the user-facing description by accident.
HELP_SECTIONS: dict[str, dict] = {
    "economy": {
        "label": "Economy",
        "emoji": "💰",
        "color": 0xF1C40F,
        "description": "Coins, pets, businesses, games, stocks, bounties, and horse races.",
        "commands": [
            ("!balance", "View your wallet, bank, net worth, and prestige."),
            ("!deposit <amount|all|half>", "Move coins from your wallet into the bank."),
            ("!withdraw <amount|all|half>", "Withdraw coins from your bank."),
            ("!daily", "Claim your daily free coins."),
            ("!weekly", "Claim your weekly reward."),
            ("!claim", "Claim rewards from your income roles."),
            ("!pay @member <amount>", "Send coins to another member."),
            ("!leaderboard", "View the richest members."),
            ("!work", "Work a random job to earn coins."),
            ("!crime", "Attempt a risky crime for a larger payout."),
            ("!rob @member", "Attempt to rob another member's wallet."),
            ("!catch @member", "Catch a wanted criminal for a reward."),
            ("!inventory", "View the items in your inventory."),
            ("!sell <item>", "Sell an item from your inventory."),
            ("!claimdrop", "Claim the active global coin or item drop."),
            ("!loan <amount|max>", "Borrow coins from the clan bank."),
            ("!repay <amount|all|half>", "Repay some or all of your loan."),
            ("!debt", "Check your current debt and interest."),
            ("!prestige", "View your wealth prestige milestones."),
            ("!shop / !buy", "Browse the pet and role shop or buy an item."),
            ("!pets", "View your pets, stats, hunger, and status."),
            ("!feed <pet> <food>", "Feed one of your pets."),
            ("!battle @member", "Battle another member's pet."),
            ("!adventures <pet>", "Send a pet on an adventure for rewards."),
            ("!sell_pet <pet>", "Sell one of your pets."),
            ("!breed <pet1> <pet2>", "Breed two pets into a stronger offspring."),
            ("!business", "Open the business empire command group."),
            ("!business shop", "Browse available business types."),
            ("!business buy <type> [name]", "Purchase a new business."),
            ("!business list [@member]", "List businesses owned by a member."),
            ("!business info <id>", "View full stats for a business."),
            ("!business collect [id]", "Collect income from one or all businesses."),
            ("!business upgrades <id>", "View available upgrades."),
            ("!business upgrade <id> <upgrade>", "Purchase a business upgrade."),
            ("!business hire <id>", "Hire a random NPC worker."),
            ("!business fire <id> <worker>", "Fire a business worker."),
            ("!business sell <id>", "Sell a business."),
            ("!business rename <id> <name>", "Rename a business."),
            ("!business visit @member", "Visit another member's business."),
            ("!business leaderboard", "View the top businesses."),
            ("!business help", "View the business command guide."),
            ("!roulette <bet> <choice>", "Bet on the casino roulette wheel."),
            ("!blackjack <bet>", "Play blackjack against the dealer."),
            ("!bjpvp @member <bet>", "Challenge another member to blackjack PvP."),
            ("!dice <bet>", "Roll two dice against the house."),
            ("!guess <bet>", "Guess a number from 0–100 in five attempts."),
            ("!8ball <question>", "Ask the magic 8-ball a question."),
            ("!horserace", "Open the multiplayer horse-race betting menu."),
            ("!horserace start", "Start a horse race with betting."),
            ("!horserace bet <horse> <amount>", "Place a bet on the active race."),
            ("!bounties", "View active bounty contracts and progress."),
            ("!stocks", "View the stock market."),
            ("!sbuy <symbol> <quantity>", "Buy shares from the market."),
            ("!ssell <symbol> <quantity>", "Sell shares to the market."),
            ("!portfolio", "View your stock portfolio."),
            ("!alert <symbol> <price>", "Get a DM when a stock reaches a price."),
            ("!myalerts", "View your active stock alerts."),
            ("!cancelalert <id>", "Cancel a stock price alert."),
            ("!autosell <symbol> <quantity> <price>", "Create an automatic sell order."),
            ("!myautosells", "View your active automatic sell orders."),
            ("!cancelautosell <id>", "Cancel an automatic sell order."),
            ("!ipo", "List a new company on the market (admin only)."),
        ],
    },
    "moderation": {
        "label": "Moderation",
        "emoji": "🛡️",
        "color": 0xE74C3C,
        "description": "Server moderation, warnings, admin economy controls, and staff tickets.",
        "commands": [
            ("!ban @member [reason]", "Ban a member (admin only)."),
            ("!unban <user_id>", "Unban a user (admin only)."),
            ("!bans", "List banned users (admin only)."),
            ("!kick @member [reason]", "Kick a member (admin only)."),
            ("!timeout @member <duration> [reason]", "Temporarily timeout a member."),
            ("!untimeout @member", "Remove a member's timeout."),
            ("!purge <amount>", "Bulk-delete messages."),
            ("!warn @member <reason>", "Issue a warning."),
            ("!warns @member", "View a member's warning history."),
            ("!delwarn <warn_id>", "Delete a specific warning."),
            ("!clearwarns @member", "Clear all warnings for a member."),
            ("!add @member <amount>", "Add coins to a member (admin only)."),
            ("!remove @member <amount>", "Remove coins from a member (admin only)."),
            ("!reset_economy", "Reset economy, pets, stocks, businesses, and bounties."),
            ("!setuproles", "Create the shop roles (admin only)."),
            ("!leaveserver <server_id>", "Make the bot leave a server (owner only)."),
            ("DM the bot", "Start a private modmail conversation with staff."),
            ("!close", "Close the current modmail ticket (staff only)."),
            ("!delete", "Delete the current modmail ticket (staff only)."),
        ],
    },
    "utilities": {
        "label": "Utilities",
        "emoji": "🧰",
        "color": 0x3498DB,
        "description": "Levels, giveaways, polls, reminders, reaction roles, starboard, and bot tools.",
        "commands": [
            ("!help", "Open this interactive command guide."),
            ("!tutorial", "Start the step-by-step economy tutorial."),
            ("!botstats", "View bot latency, uptime, servers, and members."),
            ("!afk [reason]", "Set your AFK status."),
            ("!remindme <duration> <text>", "Set a reminder for later."),
            ("!rank [@member]", "View a member's level card."),
            ("!lvltop [page]", "View the XP and level leaderboard."),
            ("!msgtop [page]", "View the message-count leaderboard."),
            ("/createlevelroles", "Create level milestone roles (admin only)."),
            ("!gstart <duration> <winners> <prize>", "Start a giveaway."),
            ("!gend <message_id>", "End a giveaway early."),
            ("!greroll <message_id>", "Reroll a giveaway winner."),
            ("!glist", "List active giveaways."),
            ("!poll <duration> <question> <options>", "Create a timed multi-option poll."),
            ("!quickpoll <question>", "Create a yes/no poll."),
            ("/reactionroles", "Open the reaction-role command group."),
            ("/reactionroles setup <channel>", "Create a reaction-role panel."),
            ("/reactionroles edit <message_id>", "Edit an existing reaction-role panel."),
            ("/reactionroles remove <message_id>", "Remove a reaction-role panel."),
            ("/reactionroles list", "List reaction-role panels in this server."),
            ("!starboard", "Open the starboard command group."),
            ("!starboard setup", "Set up or update the starboard."),
            ("!starboard config", "View the current starboard configuration."),
        ],
    },
    "other": {
        "label": "Other",
        "emoji": "✨",
        "color": 0x9B59B6,
        "description": "Fun commands, owner tools, and custom message commands.",
        "commands": [
            ("!love @member [@member]", "Calculate love compatibility."),
            ("!kiss @member [@member]", "Create an animated kiss GIF."),
            ("!impostor @member", "Toggle impostor mode (owner only)."),
            ("!say <message>", "Make the bot send a message (admin only)."),
            ("!sayembed <options>", "Send a customizable embed (admin only)."),
            ("!raise", "Hidden stock-control command."),
        ],
    },
}

HELP_COMMANDS_PER_PAGE = 12


def _help_embed(
    section_key: str,
    page: int,
    requester: discord.abc.User,
) -> tuple[discord.Embed, int]:
    section = HELP_SECTIONS[section_key]
    commands_in_section = section["commands"]
    page_count = max(1, (len(commands_in_section) + HELP_COMMANDS_PER_PAGE - 1) // HELP_COMMANDS_PER_PAGE)
    page = max(0, min(page, page_count - 1))
    start = page * HELP_COMMANDS_PER_PAGE
    page_commands = commands_in_section[start:start + HELP_COMMANDS_PER_PAGE]

    embed = discord.Embed(
        title=f"{section['emoji']} {section['label']} Commands",
        description=(
            f"{section['description']}\n\n"
            "Use the buttons below to switch sections. "
            "Commands marked with `/` are slash-only."
        ),
        color=section["color"],
    )
    for command_name, command_description in page_commands:
        embed.add_field(
            name=f"`{command_name}`",
            value=command_description,
            inline=False,
        )
    embed.set_footer(
        text=f"Page {page + 1}/{page_count} • Requested by {requester.display_name}",
        icon_url=requester.display_avatar.url,
    )
    return embed, page_count


class HelpView(discord.ui.View):
    def __init__(self, author_id: int, requester: discord.abc.User):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.requester = requester
        self.section_key = "economy"
        self.page = 0
        self.message: discord.Message | None = None
        self._build_buttons()

    async def _check_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "This help menu belongs to the person who opened it.",
            ephemeral=True,
        )
        return False

    async def _select_section(self, interaction: discord.Interaction, section_key: str):
        if not await self._check_user(interaction):
            return
        self.section_key = section_key
        self.page = 0
        await self._refresh(interaction)

    async def _change_page(self, interaction: discord.Interaction, delta: int):
        if not await self._check_user(interaction):
            return
        page_count = max(
            1,
            (len(HELP_SECTIONS[self.section_key]["commands"]) + HELP_COMMANDS_PER_PAGE - 1)
            // HELP_COMMANDS_PER_PAGE,
        )
        self.page = max(0, min(self.page + delta, page_count - 1))
        await self._refresh(interaction)

    async def _refresh(self, interaction: discord.Interaction):
        embed, _ = _help_embed(self.section_key, self.page, self.requester)
        self._build_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    def _build_buttons(self):
        self.clear_items()

        section_buttons = [
            ("economy", "Economy", "💰", discord.ButtonStyle.success),
            ("moderation", "Moderation", "🛡️", discord.ButtonStyle.danger),
            ("utilities", "Utilities", "🧰", discord.ButtonStyle.primary),
            ("other", "Other", "✨", discord.ButtonStyle.secondary),
        ]
        for section_key, label, emoji, style in section_buttons:
            button = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=style,
                disabled=self.section_key == section_key,
                row=0,
            )

            async def callback(
                interaction: discord.Interaction,
                key: str = section_key,
            ):
                await self._select_section(interaction, key)

            button.callback = callback
            self.add_item(button)

        previous = discord.ui.Button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=self.page == 0,
            row=1,
        )
        next_button = discord.ui.Button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=self.page >= max(
                1,
                (len(HELP_SECTIONS[self.section_key]["commands"]) + HELP_COMMANDS_PER_PAGE - 1)
                // HELP_COMMANDS_PER_PAGE,
            ) - 1,
            row=1,
        )

        async def previous_callback(interaction: discord.Interaction):
            await self._change_page(interaction, -1)

        async def next_callback(interaction: discord.Interaction):
            await self._change_page(interaction, 1)

        previous.callback = previous_callback
        next_button.callback = next_callback
        self.add_item(previous)
        self.add_item(next_button)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


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
        description="Open the interactive command guide.",
    )
    async def help_command(self, ctx: commands.Context):
        view = HelpView(ctx.author.id, ctx.author)
        embed, _ = _help_embed("economy", 0, ctx.author)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

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
