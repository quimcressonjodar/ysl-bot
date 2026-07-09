import asyncio
import secrets
import time

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    HORSE_NAMES,
    HORSERACE_BETTING_SECONDS,
    HORSERACE_MIN_BETTORS,
    HORSERACE_DISTANCE,
)
from utils.economy import get_user_data, update_wallet, parse_economy_amount, apply_amortization
from utils.race_gif import generate_race_gif, generate_result_image, FRAME_MS, LAST_FRAME_MS


class RaceSession:
    def __init__(self, channel_id: int, started_by: int):
        self.channel_id = channel_id
        self.started_by = started_by
        self.bets: dict[str, dict] = {}  # user_id -> {"horse": idx, "amount": int}
        self.end_time = time.time() + HORSERACE_BETTING_SECONDS
        self.message: discord.Message | None = None
        self.resolved = False
        self.lock = asyncio.Lock()


class HorseRaceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_races: dict[int, RaceSession] = {}

    def _horse_list_text(self) -> str:
        return "\n".join(f"**{i + 1}.** 🐎 {name}" for i, name in enumerate(HORSE_NAMES))

    def _bets_text(self, session: RaceSession) -> str:
        if not session.bets:
            return "_No bets placed yet._"
        lines = []
        for user_id, bet in session.bets.items():
            lines.append(f"<@{user_id}> → **{HORSE_NAMES[bet['horse']]}** (🪙 {bet['amount']:,})")
        return "\n".join(lines)

    def _build_embed(self, session: RaceSession, status: str) -> discord.Embed:
        remaining = max(0, int(session.end_time - time.time()))
        embed = discord.Embed(
            title="🏇 Horse Race",
            description=(
                f"{self._horse_list_text()}\n\n"
                f"Bet with `!horserace bet <horse 1-5> <amount>`\n"
                f"⏳ Betting closes: <t:{int(session.end_time)}:R>\n\n"
                f"**Current bets:**\n{self._bets_text(session)}"
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text=status)
        return embed

    @commands.hybrid_group(name="horserace", description="Multiplayer horse race betting game")
    async def horserace(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await self.start(ctx)

    @horserace.command(name="start", description="Start a horse race with betting")
    async def start(self, ctx: commands.Context):
        if ctx.channel.id in self.active_races:
            return await ctx.send("⚠️ There's already a race running in this channel.")

        session = RaceSession(ctx.channel.id, ctx.author.id)
        self.active_races[ctx.channel.id] = session

        embed = self._build_embed(session, "Betting is open")
        session.message = await ctx.send(embed=embed)

        asyncio.create_task(self._run_race_after_delay(ctx, session))

    @horserace.command(name="bet", description="Place a bet on the active race")
    @app_commands.describe(horse="Horse number (1-5)", amount="Amount ('all', 'half', or a number)")
    async def bet(self, ctx: commands.Context, horse: int, amount: str):
        session = self.active_races.get(ctx.channel.id)
        if session is None or session.resolved:
            return await ctx.send("❌ There's no active race in this channel. Use `!horserace start`.", ephemeral=True)

        if time.time() >= session.end_time:
            return await ctx.send("❌ Betting is already closed for this race.", ephemeral=True)

        if horse < 1 or horse > len(HORSE_NAMES):
            return await ctx.send(f"❌ Choose a horse between 1 and {len(HORSE_NAMES)}.", ephemeral=True)

        user_id = str(ctx.author.id)

        async with session.lock:
            if user_id in session.bets:
                return await ctx.send("❌ You've already placed a bet on this race.", ephemeral=True)

            user_data = get_user_data(user_id)
            bet_amount = parse_economy_amount(amount, user_data["wallet"])

            if bet_amount <= 0:
                return await ctx.send("❌ Invalid bet. Please specify a positive number, 'all', or 'half'.", ephemeral=True)
            if user_data["wallet"] < bet_amount:
                return await ctx.send(f"❌ You don't have enough coins. Your balance is 🪙 {user_data['wallet']:,}.", ephemeral=True)

            update_wallet(user_id, -bet_amount)
            session.bets[user_id] = {"horse": horse - 1, "amount": bet_amount}

        try:
            await session.message.edit(embed=self._build_embed(session, "Betting is open"))
        except (discord.NotFound, discord.HTTPException):
            pass

        await ctx.send(
            f"✅ {ctx.author.mention} bets 🪙 {bet_amount:,} on **{HORSE_NAMES[horse - 1]}**.",
            ephemeral=True,
        )

    async def _run_race_after_delay(self, ctx: commands.Context, session: RaceSession):
        delay = session.end_time - time.time()
        if delay > 0:
            await asyncio.sleep(delay)
        await self._resolve_race(ctx, session)

    async def _resolve_race(self, ctx: commands.Context, session: RaceSession):
        async with session.lock:
            session.resolved = True
            self.active_races.pop(session.channel_id, None)
            # snapshot so no late bet can mutate state while we resolve
            bets_snapshot = dict(session.bets)

        distinct_bettors = len(bets_snapshot)
        if distinct_bettors < HORSERACE_MIN_BETTORS:
            for user_id, bet in bets_snapshot.items():
                update_wallet(user_id, bet["amount"])
            embed = discord.Embed(
                title="🏇 Race cancelled",
                description=(
                    f"At least {HORSERACE_MIN_BETTORS} different players need to bet.\n"
                    "All bets have been refunded."
                ),
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        positions = [0] * len(HORSE_NAMES)
        history = [positions.copy()]
        rng = secrets.SystemRandom()
        winner_idx = None
        max_ticks = 30
        lead_changes = []  # (tick, from_idx | None, to_idx)
        current_leader = None

        for tick in range(max_ticks):
            for i in range(len(positions)):
                positions[i] += rng.randint(3, 9)
            history.append(positions.copy())

            leader = max(range(len(positions)), key=lambda i: positions[i])
            if leader != current_leader:
                lead_changes.append((tick + 1, current_leader, leader))
                current_leader = leader

            if any(p >= HORSERACE_DISTANCE for p in positions):
                break

        finishers = [i for i, p in enumerate(positions) if p >= HORSERACE_DISTANCE]
        if finishers:
            winner_idx = max(finishers, key=lambda i: positions[i])
        else:
            winner_idx = max(range(len(positions)), key=lambda i: positions[i])

        # 1) Announce the race is starting
        runners = ", ".join(HORSE_NAMES[:-1]) + f" and {HORSE_NAMES[-1]}"
        await ctx.send(f"🏇 **Racing...** {runners} are off! 🚩")

        # 2) Send the animated race GIF
        gif_buffer = generate_race_gif(history, HORSERACE_DISTANCE, winner_idx)
        gif_file = discord.File(gif_buffer, filename="race.gif")
        gif_embed = discord.Embed(title="🏇 Live Race", color=0x2ECC71)
        gif_embed.set_image(url="attachment://race.gif")
        await ctx.send(embed=gif_embed, file=gif_file)

        # let the GIF actually play out before revealing the result
        gif_duration_s = ((len(history) - 1) * FRAME_MS + LAST_FRAME_MS) / 1000
        await asyncio.sleep(min(gif_duration_s, 8.0))

        # build exciting play-by-play commentary from the lead changes
        sorted_final = sorted(range(len(positions)), key=lambda i: positions[i], reverse=True)
        margin = positions[sorted_final[0]] - positions[sorted_final[1]] if len(sorted_final) > 1 else 999
        commentary = []
        real_changes = [c for c in lead_changes if c[1] is not None]
        if len(real_changes) >= 3:
            commentary.append("🔥 What a back-and-forth battle for the lead!")
        elif len(real_changes) >= 1:
            last_change = real_changes[-1]
            commentary.append(f"⚡ **{HORSE_NAMES[last_change[2]]}** surges ahead late in the race!")
        if margin <= 4:
            commentary.append("📸 A photo finish — it came down to the wire!")
        elif margin >= 20:
            commentary.append(f"🚀 **{HORSE_NAMES[winner_idx]}** dominates, crossing the line way ahead of the pack!")

        pot = sum(bet["amount"] for bet in bets_snapshot.values())
        winners = {uid: b for uid, b in bets_snapshot.items() if b["horse"] == winner_idx}
        total_on_winner = sum(b["amount"] for b in winners.values())

        result_lines = []
        if total_on_winner > 0:
            # floor each proportional payout, then give any leftover cents from
            # rounding to the biggest bettor on the winning horse so the pot
            # is always fully distributed.
            payouts = {}
            for user_id, bet in winners.items():
                share = bet["amount"] / total_on_winner
                payouts[user_id] = int(pot * share)
            remainder = pot - sum(payouts.values())
            if remainder > 0:
                top_bettor = max(winners.items(), key=lambda kv: kv[1]["amount"])[0]
                payouts[top_bettor] += remainder

            for user_id, payout in payouts.items():
                actual_payout = apply_amortization(user_id, payout)
                update_wallet(user_id, actual_payout)
                line = f"🏆 <@{user_id}> wins 🪙 {payout:,}"
                if actual_payout < payout:
                    line += f" (🪙 {payout - actual_payout:,} used to pay off debt)"
                result_lines.append(line)
            for user_id in bets_snapshot:
                if user_id not in winners:
                    result_lines.append(f"💀 <@{user_id}> loses their bet")
        else:
            result_lines.append("💀 Nobody bet on the winner — the house keeps the pot.")
            for user_id in bets_snapshot:
                result_lines.append(f"💀 <@{user_id}> loses their bet")

        result_image = generate_result_image(positions, HORSERACE_DISTANCE, winner_idx)
        result_file = discord.File(result_image, filename="result.png")

        description_parts = []
        if commentary:
            description_parts.append("\n".join(commentary))
            description_parts.append("")
        description_parts.append("\n".join(result_lines))

        embed = discord.Embed(
            title=f"🏁 {HORSE_NAMES[winner_idx]} wins the race!",
            description="\n".join(description_parts),
            color=0xF1C40F,
        )
        embed.set_image(url="attachment://result.png")
        embed.set_footer(text=f"Total pot: 🪙 {pot:,}")

        await ctx.send(embed=embed, file=result_file)


async def setup(bot: commands.Bot):
    await bot.add_cog(HorseRaceCog(bot))
