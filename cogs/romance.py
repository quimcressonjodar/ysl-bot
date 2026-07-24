"""Playful social commands for compatibility scores and avatar kisses."""

from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils.romance import decode_avatar, love_score, love_verdict, render_kiss_gif


class RomanceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="love", description="Calculate the love compatibility between two members")
    @app_commands.describe(other="The member you want to check your love compatibility with")
    async def love(self, ctx: commands.Context, other: discord.Member):
        if other.bot:
            return await ctx.send("Bots are cute, but they are not available for romance calculations.", ephemeral=True)

        score = love_score(ctx.author.id, other.id)
        filled = round(score / 10)
        meter = "♥" * filled + "♡" * (10 - filled)
        embed = discord.Embed(
            title="Love Compatibility",
            description=(
                f"{ctx.author.mention} + {other.mention}\n\n"
                f"**{score}%**\n`{meter}`\n\n"
                f"*{love_verdict(score)}*"
            ),
            color=0xEC497B,
        )
        embed.set_footer(text="For entertainment only — the heart roll is stable for this pair.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="kiss", description="Make two members kiss in a cute animated GIF")
    @app_commands.describe(other="The member you want to kiss")
    async def kiss(self, ctx: commands.Context, other: discord.Member):
        if other.bot:
            return await ctx.send("Bots cannot kiss, but they can watch from the front row.", ephemeral=True)
        if other.id == ctx.author.id:
            return await ctx.send("You need to choose another member to kiss.", ephemeral=True)

        await ctx.defer()
        try:
            first_avatar, second_avatar = await self._download_pair(ctx.author, other)
        except (discord.HTTPException, OSError, ValueError):
            return await ctx.send(
                "I couldn't fetch one of the avatars right now. Please try again in a moment.",
                ephemeral=True,
            )

        gif = render_kiss_gif(
            first_avatar,
            second_avatar,
            ctx.author.display_name,
            other.display_name,
        )
        file = discord.File(gif, filename="ysl-kiss.gif")
        embed = discord.Embed(
            title="Kiss cam",
            description=f"{ctx.author.mention} kisses {other.mention}",
            color=0xEC497B,
        )
        embed.set_image(url="attachment://ysl-kiss.gif")
        embed.set_footer(text="A tiny YSL love story")
        await ctx.send(embed=embed, file=file)

    @staticmethod
    async def _download_pair(
        first: discord.abc.User,
        second: discord.abc.User,
    ):
        first_bytes, second_bytes = await asyncio.gather(
            first.display_avatar.with_size(256).read(),
            second.display_avatar.with_size(256).read(),
        )
        return decode_avatar(first_bytes), decode_avatar(second_bytes)


async def setup(bot: commands.Bot):
    await bot.add_cog(RomanceCog(bot))