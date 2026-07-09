import asyncio
import random
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
from utils.race_gif import generate_race_gif


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
            return "_Nadie ha apostado todavía._"
        lines = []
        for user_id, bet in session.bets.items():
            lines.append(f"<@{user_id}> → **{HORSE_NAMES[bet['horse']]}** (🪙 {bet['amount']:,})")
        return "\n".join(lines)

    def _build_embed(self, session: RaceSession, status: str) -> discord.Embed:
        remaining = max(0, int(session.end_time - time.time()))
        embed = discord.Embed(
            title="🏇 Carrera de Caballos",
            description=(
                f"{self._horse_list_text()}\n\n"
                f"Apuesta con `!horserace bet <caballo 1-5> <cantidad>`\n"
                f"⏳ Cierre de apuestas: <t:{int(session.end_time)}:R>\n\n"
                f"**Apuestas actuales:**\n{self._bets_text(session)}"
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text=status)
        return embed

    @commands.hybrid_group(name="horserace", description="Carrera de caballos multijugador")
    async def horserace(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await self.start(ctx)

    @horserace.command(name="start", description="Inicia una carrera de caballos con apuestas")
    async def start(self, ctx: commands.Context):
        if ctx.channel.id in self.active_races:
            return await ctx.send("⚠️ Ya hay una carrera en curso en este canal.")

        session = RaceSession(ctx.channel.id, ctx.author.id)
        self.active_races[ctx.channel.id] = session

        embed = self._build_embed(session, "Fase de apuestas abierta")
        session.message = await ctx.send(embed=embed)

        asyncio.create_task(self._run_race_after_delay(ctx, session))

    @horserace.command(name="bet", description="Apuesta en la carrera activa")
    @app_commands.describe(horse="Número del caballo (1-5)", amount="Cantidad ('all', 'half' o número)")
    async def bet(self, ctx: commands.Context, horse: int, amount: str):
        session = self.active_races.get(ctx.channel.id)
        if session is None or session.resolved:
            return await ctx.send("❌ No hay ninguna carrera activa en este canal. Usa `!horserace start`.", ephemeral=True)

        if time.time() >= session.end_time:
            return await ctx.send("❌ Las apuestas ya están cerradas para esta carrera.", ephemeral=True)

        if horse < 1 or horse > len(HORSE_NAMES):
            return await ctx.send(f"❌ Elige un caballo entre 1 y {len(HORSE_NAMES)}.", ephemeral=True)

        user_id = str(ctx.author.id)

        async with session.lock:
            if user_id in session.bets:
                return await ctx.send("❌ Ya has apostado en esta carrera.", ephemeral=True)

            user_data = get_user_data(user_id)
            bet_amount = parse_economy_amount(amount, user_data["wallet"])

            if bet_amount <= 0:
                return await ctx.send("❌ Apuesta inválida. Usa un número positivo, 'all' o 'half'.", ephemeral=True)
            if user_data["wallet"] < bet_amount:
                return await ctx.send(f"❌ No tienes suficientes monedas. Tu saldo es 🪙 {user_data['wallet']:,}.", ephemeral=True)

            update_wallet(user_id, -bet_amount)
            session.bets[user_id] = {"horse": horse - 1, "amount": bet_amount}

        try:
            await session.message.edit(embed=self._build_embed(session, "Fase de apuestas abierta"))
        except (discord.NotFound, discord.HTTPException):
            pass

        await ctx.send(
            f"✅ {ctx.author.mention} apuesta 🪙 {bet_amount:,} a **{HORSE_NAMES[horse - 1]}**.",
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
                title="🏇 Carrera cancelada",
                description=(
                    f"Se necesitan al menos {HORSERACE_MIN_BETTORS} jugadores distintos apostando.\n"
                    "Todas las apuestas han sido reembolsadas."
                ),
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        positions = [0] * len(HORSE_NAMES)
        history = [positions.copy()]
        rng = secrets.SystemRandom()
        winner_idx = None
        max_ticks = 30

        for _ in range(max_ticks):
            for i in range(len(positions)):
                positions[i] += rng.randint(3, 9)
            history.append(positions.copy())
            if any(p >= HORSERACE_DISTANCE for p in positions):
                break

        finishers = [i for i, p in enumerate(positions) if p >= HORSERACE_DISTANCE]
        if finishers:
            winner_idx = max(finishers, key=lambda i: positions[i])
        else:
            winner_idx = max(range(len(positions)), key=lambda i: positions[i])

        gif_buffer = generate_race_gif(history, HORSERACE_DISTANCE, winner_idx)
        gif_file = discord.File(gif_buffer, filename="race.gif")

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
                line = f"🏆 <@{user_id}> gana 🪙 {payout:,}"
                if actual_payout < payout:
                    line += f" (🪙 {payout - actual_payout:,} usado para pagar deuda)"
                result_lines.append(line)
            for user_id in bets_snapshot:
                if user_id not in winners:
                    result_lines.append(f"💀 <@{user_id}> pierde su apuesta")
        else:
            result_lines.append("💀 Nadie apostó al ganador — la casa se queda con el bote.")
            for user_id in bets_snapshot:
                result_lines.append(f"💀 <@{user_id}> pierde su apuesta")

        embed = discord.Embed(
            title=f"🏁 ¡{HORSE_NAMES[winner_idx]} gana la carrera!",
            description="\n".join(result_lines),
            color=0xF1C40F,
        )
        embed.set_image(url="attachment://race.gif")
        embed.set_footer(text=f"Bote total: 🪙 {pot:,}")

        await ctx.send(embed=embed, file=gif_file)


async def setup(bot: commands.Bot):
    await bot.add_cog(HorseRaceCog(bot))
