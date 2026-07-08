"""
Business Cog - Discord interface for the complete Business System.
Commands grouped under /business (hybrid: slash + prefix).
"""
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import time as _time
from database import pets_col, eco_col
from utils.economy import get_wallet, update_wallet
from utils.pets import get_current_hunger
from utils.business import (
  BUSINESS_TYPES,
  get_business, get_owner_businesses,
  compute_income, collect_income,
  buy_business, apply_upgrade,
  hire_worker, fire_worker,
  sell_business, rename_business,
  visit_business, increment_visits,
  get_leaderboard, get_xp_for_next_level,
  XP_PER_LEVEL, businesses_col,
)


# ─────────────────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────────────────

class BusinessListView(discord.ui.View):
  """Paginated embed showing all businesses owned by a user."""
  PER_PAGE = 4

  def __init__(self, ctx: commands.Context, businesses: list[dict]):
      super().__init__(timeout=60)
      self.ctx        = ctx
      self.businesses = businesses
      self.page       = 0
      self.message: discord.Message | None = None

  async def on_timeout(self) -> None:
      if self.message:
          try:
              await self.message.edit(view=None)
          except Exception:
              pass

  def max_pages(self) -> int:
      return max(1, (len(self.businesses) + self.PER_PAGE - 1) // self.PER_PAGE)

  def build_embed(self) -> discord.Embed:
      embed = discord.Embed(
          title=f"\U0001f3e2 {self.ctx.author.display_name}'s Businesses",
          color=0x2ECC71,
      )
      start = self.page * self.PER_PAGE
      for b in self.businesses[start : start + self.PER_PAGE]:
          btype = BUSINESS_TYPES[b["type"]]
          info  = compute_income(b)
          embed.add_field(
              name=f'{btype["emoji"]} {b["name"]} (Lv.{b["level"]})',
              value=(
                  f'\U0001f194 `{b["_id"]}`\n'
                  f'\U0001f4c8 Pending: \U0001fa99 **{info["net"]:,}** ({info["hours_pending"]:.1f}h)\n'
                  f'\u2b50 Rep: {b.get("reputation", 50)}/100  '
                  f'\U0001f477 Workers: {len(b["workers"])}/{btype["max_workers"]}'
              ),
              inline=False,
          )
      embed.set_footer(text=f'Page {self.page+1}/{self.max_pages()} \u2022 /business info <id> for full details')
      return embed

  async def _guard(self, interaction: discord.Interaction) -> bool:
      if str(interaction.user.id) != str(self.ctx.author.id):
          await interaction.response.send_message("\u274c Not your menu.", ephemeral=True)
          return False
      return True

  @discord.ui.button(label="\u25c4", style=discord.ButtonStyle.secondary)
  async def prev_page(self, interaction: discord.Interaction, _: discord.ui.Button):
      if not await self._guard(interaction):
          return
      self.page = max(0, self.page - 1)
      await interaction.response.edit_message(embed=self.build_embed(), view=self)

  @discord.ui.button(label="\u25ba", style=discord.ButtonStyle.secondary)
  async def next_page(self, interaction: discord.Interaction, _: discord.ui.Button):
      if not await self._guard(interaction):
          return
      self.page = min(self.max_pages() - 1, self.page + 1)
      await interaction.response.edit_message(embed=self.build_embed(), view=self)


class SellConfirmView(discord.ui.View):
  def __init__(self, ctx: commands.Context, business_id: str, sell_price: int, name: str):
      super().__init__(timeout=30)
      self.ctx         = ctx
      self.business_id = business_id
      self.sell_price  = sell_price
      self.name        = name
      self.message: discord.Message | None = None

  async def on_timeout(self) -> None:
      if self.message:
          try:
              await self.message.edit(content="⏰ This confirmation expired.", view=None, embed=None)
          except Exception:
              pass

  @discord.ui.button(label="\u2705 Confirm Sale", style=discord.ButtonStyle.danger)
  async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Not your menu.", ephemeral=True)
      result = sell_business(self.business_id)
      if "error" in result:
          return await interaction.response.edit_message(content=f'\u274c {result["error"]}', view=None, embed=None)
      update_wallet(str(interaction.user.id), result["sell_price"])
      embed = discord.Embed(
          title="\U0001f4b0 Business Sold!",
          description=f'You sold **{result["name"]}** for \U0001fa99 **{result["sell_price"]:,}**.\nFunds added to your wallet.',
          color=0xE74C3C,
      )
      await interaction.response.edit_message(embed=embed, view=None)

  @discord.ui.button(label="\u274c Cancel", style=discord.ButtonStyle.secondary)
  async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Not your menu.", ephemeral=True)
      await interaction.response.edit_message(content="Sale cancelled.", embed=None, view=None)


class HireConfirmView(discord.ui.View):
  def __init__(self, ctx: commands.Context, business_id: str, worker: dict, hire_cost: int):
      super().__init__(timeout=30)
      self.ctx         = ctx
      self.business_id = business_id
      self.worker      = worker
      self.hire_cost   = hire_cost
      self._confirmed  = False
      self.message: discord.Message | None = None

  async def on_timeout(self) -> None:
      if self.message:
          try:
              await self.message.edit(content="⏰ This confirmation expired.", view=None, embed=None)
          except Exception:
              pass

  @discord.ui.button(label="\u2705 Hire", style=discord.ButtonStyle.green)
  async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Not your menu.", ephemeral=True)
      self._confirmed = True
      w = self.worker
      update_wallet(str(interaction.user.id), -self.hire_cost)
      embed = discord.Embed(
          title="\U0001f477 Worker Hired!",
          description=(
              f'**{w["name"]}** ({w["role"]}) joined your business!\n\n'
              f'\U0001fa99 Salary: {w["salary"]:,}/hr\n'
              f'\u2699\ufe0f Efficiency: {w["efficiency"]:.2f}x\n'
              f'\U0001fa99 Hiring fee deducted: **{self.hire_cost:,}**'
          ),
          color=0x2ECC71,
      )
      await interaction.response.edit_message(embed=embed, view=None)

  @discord.ui.button(label="\u274c Cancel", style=discord.ButtonStyle.secondary)
  async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Not your menu.", ephemeral=True)
      if not self._confirmed:
          b = get_business(self.business_id)
          if b and b.get("workers"):
              workers = b["workers"]
              workers.pop()
              businesses_col.update_one({"_id": self.business_id}, {"$set": {"workers": workers}})
      await interaction.response.edit_message(content="Hiring cancelled.", embed=None, view=None)


class VisitView(discord.ui.View):
  """Select menu to visit another player's business and pay the entry fee."""

  def __init__(self, ctx: commands.Context, owner: discord.Member, businesses: list[dict]):
      super().__init__(timeout=60)
      self.ctx   = ctx
      self.owner = owner
      self.message: discord.Message | None = None
      options = []
      for b in businesses[:25]:
          btype = BUSINESS_TYPES[b["type"]]
          fee   = btype.get("entry_fee", 0)
          options.append(discord.SelectOption(
              label=f'{b["name"][:50]} (Lv.{b["level"]})',
              description=f'{btype["name"]} \u2022 Entry: \U0001fa99 {fee:,}',
              value=b["_id"],
              emoji=btype["emoji"],
          ))
      self.select.options = options

  async def on_timeout(self) -> None:
      if self.message:
          try:
              await self.message.edit(content="⏰ This visit menu expired.", view=None, embed=None)
          except Exception:
              pass

  @discord.ui.select(placeholder="Choose a business to visit\u2026", min_values=1, max_values=1)
  async def select(self, interaction: discord.Interaction, sel: discord.ui.Select):
      if str(interaction.user.id) != str(self.ctx.author.id):
          return await interaction.response.send_message("\u274c Not your menu.", ephemeral=True)
      await interaction.response.defer()
      business_id = sel.values[0]
      b = get_business(business_id)
      if not b:
          return await interaction.followup.send("\u274c Business not found.", ephemeral=True)
      btype    = BUSINESS_TYPES[b["type"]]
      fee      = btype.get("entry_fee", 0)
      visitor  = str(interaction.user.id)
      owner_id = b["owner_id"]
      if visitor == owner_id:
          return await interaction.followup.send("\u274c That is your own business.", ephemeral=True)
      wallet = get_wallet(visitor)
      if wallet < fee:
          return await interaction.followup.send(
              f"\u274c You need \U0001fa99 **{fee:,}** and you have \U0001fa99 {wallet:,}.",
              ephemeral=True,
          )
      result = visit_business(visitor, business_id)
      if "error" in result:
          return await interaction.followup.send(f'\u274c {result["error"]}', ephemeral=True)

      # ── Deduct entry fee & pay owner ──────────────────────
      update_wallet(visitor,  -fee)
      update_wallet(owner_id,  fee)

      # ── Apply visitor benefit ─────────────────────────────
      benefit      = result.get("visit_benefit", {"type": "none", "value": 0})
      benefit_type = benefit.get("type", "none")
      benefit_val  = benefit.get("value", 0)
      benefit_line = ""

      if benefit_type == "feed_pets":
          # Feed all pets the visitor owns
          owner_data = pets_col.find_one({"_id": visitor})
          if owner_data and owner_data.get("pets"):
              pets = owner_data["pets"]
              now  = _time.time()
              fed_count = 0
              for pet in pets:
                  current_hunger = get_current_hunger(pet)
                  new_hunger     = min(100, current_hunger + benefit_val)
                  pet["hunger"]   = new_hunger
                  pet["last_fed"] = now
                  fed_count += 1
              pets_col.update_one({"_id": visitor}, {"$set": {"pets": pets}})
              benefit_line = f"\U0001f43e **Pets fed:** {fed_count} pet(s) +{benefit_val} hunger"
          else:
              benefit_line = "\U0001f43e No pets to feed — get a pet to enjoy this perk!"

      elif benefit_type == "coins":
          update_wallet(visitor, benefit_val)
          benefit_line = f"\U0001fa99 **Bonus earned:** {benefit_val:,} coins"

      elif benefit_type == "strength":
          eco_col.update_one(
              {"_id": visitor},
              {"$inc": {"strength": benefit_val}},
              upsert=True,
          )
          user_data = eco_col.find_one({"_id": visitor}) or {}
          total_str = user_data.get("strength", benefit_val)
          benefit_line = f"\U0001f4aa **Strength gained:** +{benefit_val} XP (Total: {total_str:,})"

      embed = discord.Embed(
          title=f'{btype["emoji"]} Visit Complete!',
          description=(
              f'{result["visit_description"]}\n\n'
              f'\U0001f3e2 **{b["name"]}** owned by {self.owner.display_name}\n'
              f'\U0001f4b8 You paid: \U0001fa99 **{fee:,}**\n'
              f'\U0001f464 Owner received: \U0001fa99 **{fee:,}**\n'
              f'{benefit_line}'
          ),
          color=0x2ecc71,
      )
      embed.set_footer(text=f"Total visits: {b.get('visits', 0) + 1:,}")
      await interaction.edit_original_response(embed=embed, view=None)


# ─────────────────────────────────────────────────────────
# COG
# ─────────────────────────────────────────────────────────

class BusinessCog(commands.Cog):
  def __init__(self, bot: commands.Bot):
      self.bot = bot

  @commands.hybrid_group(name="business", description="Manage your business empire")
  async def business(self, ctx: commands.Context):
      if ctx.invoked_subcommand is None:
          await ctx.send("Use `/business shop` to browse types or `/business help` for all commands.", ephemeral=True)

  # ── /business shop ────────────────────────────────────
  @business.command(name="shop", description="Browse all available business types")
  async def business_shop(self, ctx: commands.Context):
      embed = discord.Embed(
          title="\U0001f3ea Business Marketplace",
          description="Use `/business buy <type> [name]` to open one.",
          color=0xF39C12,
      )
      for key, b in BUSINESS_TYPES.items():
          embed.add_field(
              name=f'{b["emoji"]} {b["name"]}  `{key}`',
              value=(
                  f'\U0001f4b0 Cost: \U0001fa99 **{b["base_cost"]:,}**\n'
                  f'\U0001f4c8 Income: \U0001fa99 **{b["base_income_per_hour"]:,}**/hr\n'
                  f'\U0001f527 Maint: \U0001fa99 **{b["base_maintenance_per_hour"]:,}**/hr\n'
                  f'\U0001f477 Max workers: **{b["max_workers"]}**'
              ),
              inline=True,
          )
      embed.set_footer(text="Net profit depends on level, upgrades, workers & reputation.")
      await ctx.send(embed=embed)

  # ── /business buy ─────────────────────────────────────
  @business.command(name="buy", description="Purchase a new business")
  @app_commands.describe(type="Business type key (e.g. restaurant, cinema, arcade)", name="Custom name (optional)")
  async def business_buy(self, ctx: commands.Context, type: str, *, name: str = ""):
      btype_key = type.lower().replace(" ", "").replace("_", "").replace("-", "")
      if btype_key not in BUSINESS_TYPES:
          keys = ", ".join(f"`{k}`" for k in BUSINESS_TYPES)
          return await ctx.send(f"\u274c Unknown type. Valid types: {keys}", ephemeral=True)

      btype   = BUSINESS_TYPES[btype_key]
      cost    = btype["base_cost"]
      user_id = str(ctx.author.id)
      wallet  = get_wallet(user_id)

      if wallet < cost:
          return await ctx.send(
              f'\u274c You need \U0001fa99 **{cost:,}** to open a {btype["name"]}. You have \U0001fa99 {wallet:,}.',
              ephemeral=True,
          )

      name = (name or f"{ctx.author.display_name}'s {btype['name']}")[:40]
      update_wallet(user_id, -cost)
      result = buy_business(user_id, btype_key, name)

      embed = discord.Embed(
          title='\U0001f389 Business Opened!',
          description=(
              f'{btype["emoji"]} You now own **{name}**!\n\n'
              f'\U0001f4b0 Paid: \U0001fa99 {cost:,}\n'
              f'\U0001f4c8 Income: \U0001fa99 {btype["base_income_per_hour"]:,}/hr\n'
              f'\U0001f527 Maintenance: \U0001fa99 {btype["base_maintenance_per_hour"]:,}/hr\n'
              f'\U0001f477 Max workers: {btype["max_workers"]}\n\n'
              f'\U0001f194 Business ID: `{result["business_id"]}`\n'
              f'Collect income with `/business collect`!'
          ),
          color=0x2ECC71,
      )
      await ctx.send(embed=embed)

  # ── /business list ────────────────────────────────────
  @business.command(name="list", description="View all businesses you or another player owns")
  @app_commands.describe(member="Player to look up (default: you)")
  async def business_list(self, ctx: commands.Context, member: discord.Member = None):
      target     = member or ctx.author
      businesses = get_owner_businesses(str(target.id))
      pronoun    = "You have" if not member else f"{target.display_name} has"
      if not businesses:
          return await ctx.send(f"{pronoun} no businesses yet.", ephemeral=True)
      view = BusinessListView(ctx, businesses)
      view.message = await ctx.send(embed=view.build_embed(), view=view)

  # ── /business info ────────────────────────────────────
  @business.command(name="info", description="Full stats for a specific business")
  @app_commands.describe(business_id="The business ID (see /business list)")
  async def business_info(self, ctx: commands.Context, business_id: str):
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Business not found.", ephemeral=True)

      btype   = BUSINESS_TYPES[b["type"]]
      info    = compute_income(b)
      level   = b.get("level", 1)
      xp      = b.get("xp", 0)
      next_xp = get_xp_for_next_level(level)
      founded = datetime.fromtimestamp(b["founded_at"], tz=timezone.utc).strftime("%Y-%m-%d")

      if str(ctx.author.id) != b["owner_id"]:
          increment_visits(business_id)

      upgrades_owned = b.get("upgrades", [])
      upg_lines = []
      for uid, upg in btype["upgrades"].items():
          if uid in upgrades_owned:
              status = "\u2705 Owned"
          elif level < upg["req_level"]:
              status = f'\U0001f512 Lv.{upg["req_level"]} required'
          else:
              status = f'\U0001f6d2 \U0001fa99 {upg["cost"]:,}'
          upg_lines.append(f'{upg["emoji"]} **{upg["name"]}** \u2014 {status} (+{int(upg["income_bonus"]*100)}%)')

      workers      = b.get("workers", [])
      worker_lines = [
          f'`#{i}` **{w["name"]}** ({w["role"]}) \u2014 \U0001fa99{w["salary"]:,}/hr | \u2699\ufe0f{w["efficiency"]:.2f}x | Lv.{w["level"]}'
          for i, w in enumerate(workers)
      ] or ["*No workers hired.*"]

      embed = discord.Embed(
          title=f'{btype["emoji"]} {b["name"]}',
          description=f'*{btype["description"]}*',
          color=0x3498DB,
      )
      embed.add_field(name="\U0001f4ca Overview", value=(
          f'\U0001f3c6 Level: **{level}** \u2014 XP: {xp}/{next_xp}\n'
          f'\u2b50 Reputation: **{b.get("reputation", 50)}/100**\n'
          f'\U0001f4c5 Founded: {founded}\n'
          f'\U0001f440 Visits: {b.get("visits", 0):,}'
      ), inline=False)
      embed.add_field(name="\U0001f4b5 Financials", value=(
          f'\U0001f4c8 Gross ({info["hours_pending"]:.1f}h): \U0001fa99 {info["gross_income"]:,}\n'
          f'\U0001f527 Maintenance: \U0001fa99 {info["maintenance"]:,}\n'
          f'\U0001f477 Salaries: \U0001fa99 {info["worker_salaries"]:,}\n'
          f'\U0001f4b0 **Net Profit: \U0001fa99 {info["net"]:,}**\n'
          f'\U0001f4e6 All-time Earned: \U0001fa99 {b.get("total_earned", 0):,}'
      ), inline=False)
      embed.add_field(
          name=f'\U0001f3d7\ufe0f Upgrades ({len(upgrades_owned)}/{len(btype["upgrades"])})',
          value="\n".join(upg_lines),
          inline=False,
      )
      embed.add_field(
          name=f'\U0001f477 Workers ({len(workers)}/{btype["max_workers"]})',
          value="\n".join(worker_lines)[:1000],
          inline=False,
      )
      embed.set_footer(text=f"Business ID: {business_id}")
      await ctx.send(embed=embed)

  # ── /business collect ─────────────────────────────────
  @business.command(name="collect", description="Collect income from all or one specific business")
  @commands.cooldown(1, 1800, commands.BucketType.user)
  @app_commands.describe(business_id="Leave blank to collect from ALL your businesses")
  async def business_collect(self, ctx: commands.Context, business_id: str = None):
      user_id = str(ctx.author.id)
      if business_id:
          b = get_business(business_id)
          if not b:
              return await ctx.send("\u274c Business not found.", ephemeral=True)
          if b["owner_id"] != user_id:
              return await ctx.send("\u274c That is not your business.", ephemeral=True)
          businesses = [b]
      else:
          businesses = get_owner_businesses(user_id)
          if not businesses:
              return await ctx.send("\u274c You don't own any businesses.", ephemeral=True)

      total_net = 0
      total_xp  = 0
      level_ups = []
      lines     = []

      for b in businesses:
          btype  = BUSINESS_TYPES[b["type"]]
          result = collect_income(b["_id"])
          net    = max(0, result["net"])
          total_net += net
          total_xp  += result["xp_earned"]
          if result.get("leveled_up"):
              level_ups.append(f'{btype["emoji"]} **{b["name"]}** reached Level {result["new_level"]}! \U0001f389')
          lines.append(f'{btype["emoji"]} **{b["name"]}** \u2014 \U0001fa99 {net:,} (+{result["xp_earned"]} XP)')

      if total_net > 0:
          update_wallet(user_id, total_net)

      embed = discord.Embed(
          title="\U0001f4b0 Income Collected!",
          description="\n".join(lines) or "Nothing to collect right now.",
          color=0xF1C40F,
      )
      embed.add_field(name="\U0001f4b5 Total", value=f"\U0001fa99 **{total_net:,}**", inline=True)
      embed.add_field(name="\u2b50 XP",        value=f"**+{total_xp}**",              inline=True)
      if level_ups:
          embed.add_field(name="\U0001f3c6 Level Ups!", value="\n".join(level_ups), inline=False)
      await ctx.send(embed=embed)

  # ── /business upgrades ────────────────────────────────
  @business.command(name="upgrades", description="View all upgrades for a business")
  @app_commands.describe(business_id="Business ID")
  async def business_upgrades(self, ctx: commands.Context, business_id: str):
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Business not found.", ephemeral=True)
      btype = BUSINESS_TYPES[b["type"]]
      level = b.get("level", 1)
      owned = b.get("upgrades", [])
      embed = discord.Embed(
          title=f'\U0001f3d7\ufe0f Upgrades \u2014 {b["name"]}',
          description=f'Level: **{level}**  \u2022  Buy with `/business upgrade {business_id} <id>`',
          color=0x9B59B6,
      )
      for uid, upg in btype["upgrades"].items():
          if uid in owned:
              status = "\u2705 **Owned**"
          elif level < upg["req_level"]:
              status = f'\U0001f512 Requires Level {upg["req_level"]}'
          else:
              status = f'\U0001f6d2 Buy for \U0001fa99 {upg["cost"]:,}'
          embed.add_field(
              name=f'{upg["emoji"]} {upg["name"]}  `{uid}`',
              value=f'{status}\n\U0001f4c8 +{int(upg["income_bonus"]*100)}% income',
              inline=True,
          )
      await ctx.send(embed=embed)

  # ── /business upgrade ─────────────────────────────────
  @business.command(name="upgrade", description="Purchase an upgrade for one of your businesses")
  @app_commands.describe(business_id="Business ID", upgrade_id="Upgrade key (see /business upgrades)")
  async def business_upgrade(self, ctx: commands.Context, business_id: str, upgrade_id: str):
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Business not found.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c That is not your business.", ephemeral=True)

      btype   = BUSINESS_TYPES[b["type"]]
      upgrade = btype["upgrades"].get(upgrade_id)
      if not upgrade:
          available = ", ".join(f"`{k}`" for k in btype["upgrades"])
          return await ctx.send(f"\u274c Invalid upgrade. Available: {available}", ephemeral=True)

      wallet = get_wallet(user_id)
      if wallet < upgrade["cost"]:
          return await ctx.send(
              f'\u274c You need \U0001fa99 **{upgrade["cost"]:,}**. You have \U0001fa99 {wallet:,}.', ephemeral=True
          )

      result = apply_upgrade(business_id, upgrade_id)
      if "error" in result:
          return await ctx.send(f'\u274c {result["error"]}', ephemeral=True)

      update_wallet(user_id, -upgrade["cost"])
      embed = discord.Embed(
          title="\U0001f3d7\ufe0f Upgrade Applied!",
          description=(
              f'{upgrade["emoji"]} **{upgrade["name"]}** installed in **{b["name"]}**!\n'
              f'\U0001f4c8 Income bonus: **+{int(upgrade["income_bonus"]*100)}%**\n'
              f'\U0001fa99 Cost: {upgrade["cost"]:,}'
          ),
          color=0x9B59B6,
      )
      await ctx.send(embed=embed)

  # ── /business hire ────────────────────────────────────
  @business.command(name="hire", description="Hire a random NPC worker for a business")
  @app_commands.describe(business_id="Business ID")
  async def business_hire(self, ctx: commands.Context, business_id: str):
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Business not found.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c That is not your business.", ephemeral=True)

      result = hire_worker(business_id)
      if "error" in result:
          return await ctx.send(f'\u274c {result["error"]}', ephemeral=True)

      w, cost = result["worker"], result["hire_cost"]
      wallet  = get_wallet(user_id)
      if wallet < cost:
          b2 = get_business(business_id)
          if b2 and b2.get("workers"):
              workers = b2["workers"]
              workers.pop()
              businesses_col.update_one({"_id": business_id}, {"$set": {"workers": workers}})
          return await ctx.send(
              f'\u274c You need \U0001fa99 **{cost:,}** (hiring fee = 5\u00d7 hourly salary). You have \U0001fa99 {wallet:,}.',
              ephemeral=True,
          )

      embed = discord.Embed(
          title="\U0001f477 Worker Available!",
          description=(
              f'**{w["name"]}** wants to join as **{w["role"]}**.\n\n'
              f'\U0001fa99 Salary: {w["salary"]:,}/hr\n'
              f'\u2699\ufe0f Efficiency: {w["efficiency"]:.2f}x\n'
              f'\U0001fa99 Hiring fee (5\u00d7 salary): **{cost:,}**\n\n'
              f'*Salary is deducted automatically on every collect.*'
          ),
          color=0x27AE60,
      )
      view = HireConfirmView(ctx, business_id, w, cost)
      view.message = await ctx.send(embed=embed, view=view)

  # ── /business fire ────────────────────────────────────
  @business.command(name="fire", description="Fire a worker from one of your businesses")
  @app_commands.describe(business_id="Business ID", worker_index="Worker # (see /business info)")
  async def business_fire(self, ctx: commands.Context, business_id: str, worker_index: int):
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Business not found.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c That is not your business.", ephemeral=True)
      result = fire_worker(business_id, worker_index)
      if "error" in result:
          return await ctx.send(f'\u274c {result["error"]}', ephemeral=True)
      w = result["fired"]
      await ctx.send(embed=discord.Embed(
          title="\U0001f534 Worker Fired",
          description=f'**{w["name"]}** ({w["role"]}) has been let go from **{b["name"]}**.',
          color=0xE74C3C,
      ))

  # ── /business sell ────────────────────────────────────
  @business.command(name="sell", description="Sell a business and receive coins")
  @app_commands.describe(business_id="Business ID")
  async def business_sell(self, ctx: commands.Context, business_id: str):
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Business not found.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c That is not your business.", ephemeral=True)

      btype          = BUSINESS_TYPES[b["type"]]
      upgrades_owned = b.get("upgrades", [])
      upgrade_val    = sum(btype["upgrades"][u]["cost"] for u in upgrades_owned if u in btype["upgrades"])
      level          = b.get("level", 1)
      sell_price     = int((btype["base_cost"] + upgrade_val) * btype["sell_multiplier"] * (1 + (level - 1) * 0.05))

      embed = discord.Embed(
          title="\u26a0\ufe0f Sell Business?",
          description=(
              f'Sell **{b["name"]}**?\n\n'
              f'\U0001fa99 You will receive: **{sell_price:,}**\n'
              f'*(60% of cost + upgrades + {(level-1)*5}% level bonus \u2014 this cannot be undone!)*'
          ),
          color=0xE67E22,
      )
      view = SellConfirmView(ctx, business_id, sell_price, b["name"])
      view.message = await ctx.send(embed=embed, view=view)

  # ── /business rename ──────────────────────────────────
  @business.command(name="rename", description="Give a business a new name")
  @app_commands.describe(business_id="Business ID", name="New name (max 40 chars)")
  async def business_rename(self, ctx: commands.Context, business_id: str, *, name: str):
      user_id = str(ctx.author.id)
      b = get_business(business_id)
      if not b:
          return await ctx.send("\u274c Business not found.", ephemeral=True)
      if b["owner_id"] != user_id:
          return await ctx.send("\u274c That is not your business.", ephemeral=True)
      rename_business(business_id, name[:40])
      await ctx.send(f'\u2705 Renamed to **{name[:40]}**!', ephemeral=True)

  # ── /business visit ───────────────────────────────────
  @business.command(name="visit", description="Visit another player's business and pay the entry fee")
  @app_commands.describe(member="The player whose business you want to visit")
  async def business_visit(self, ctx: commands.Context, member: discord.Member):
      if member.id == ctx.author.id:
          return await ctx.send("Use `/business list` to see your own businesses.", ephemeral=True)
      businesses = get_owner_businesses(str(member.id))
      if not businesses:
          return await ctx.send(f"**{member.display_name}** has no businesses yet.", ephemeral=True)

      embed = discord.Embed(
          title=f"\U0001f3e2 {member.display_name}'s Businesses",
          description=f"Choose a business to visit. **{member.display_name}** will receive the entry fee instantly.",
          color=0x3498DB,
      )
      for b in businesses[:8]:
          btype = BUSINESS_TYPES[b["type"]]
          fee   = btype.get("entry_fee", 0)
          embed.add_field(
              name=f'{btype["emoji"]} {b["name"]} (Lv.{b["level"]})',
              value=(
                  f'\U0001f3ab Entry: \U0001fa99 **{fee:,}**\n'
                  f'\u2b50 Rep: {b.get("reputation", 50)}/100  '
                  f'\U0001f440 Visits: {b.get("visits", 0):,}'
              ),
              inline=True,
          )
      embed.set_thumbnail(url=member.display_avatar.url)
      view = VisitView(ctx, member, businesses)
      view.message = await ctx.send(embed=embed, view=view)

  # ── /business leaderboard ─────────────────────────────
  @business.command(name="leaderboard", description="Top 10 businesses by total earnings")
  async def business_leaderboard(self, ctx: commands.Context):
      top    = get_leaderboard(10)
      medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
      embed  = discord.Embed(title="\U0001f3c6 Business Leaderboard", color=0xF1C40F)
      for i, b in enumerate(top):
          btype = BUSINESS_TYPES.get(b["type"], {})
          emoji = btype.get("emoji", "\U0001f3e2")
          medal = medals[i] if i < 3 else f"#{i+1}"
          try:
              owner      = await self.bot.fetch_user(int(b["owner_id"]))
              owner_name = owner.display_name
          except Exception:
              owner_name = f'User {b["owner_id"]}'
          embed.add_field(
              name=f'{medal} {emoji} {b["name"]} (Lv.{b.get("level", 1)})',
              value=f'\U0001f464 {owner_name} \u2014 \U0001fa99 {b.get("total_earned", 0):,} earned',
              inline=False,
          )
      await ctx.send(embed=embed)

  # ── /business help ────────────────────────────────────
  @business.command(name="help", description="All business system commands explained")
  async def business_help(self, ctx: commands.Context):
      embed = discord.Embed(title="\U0001f4d6 Business System \u2014 Commands", color=0x8E44AD)
      for cmd, desc in [
          ("/business shop",                   "Browse all business types & prices"),
          ("/business buy <type> [name]",       "Open a new business"),
          ("/business list [member]",            "View your (or someone's) businesses"),
          ("/business info <id>",                "Full stats: income, workers, upgrades, XP"),
          ("/business collect [id]",             "Collect pending income (all or one)"),
          ("/business upgrades <id>",            "See all upgrades for a business"),
          ("/business upgrade <id> <upgrade>",   "Purchase an upgrade"),
          ("/business hire <id>",                "Hire a random NPC worker"),
          ("/business fire <id> <#>",            "Fire a worker by index"),
          ("/business sell <id>",                "Sell a business for coins"),
          ("/business rename <id> <name>",       "Rename a business"),
          ("/business visit <member>",           "Visit another player's business"),
          ("/business leaderboard",              "Top 10 earners globally"),
      ]:
          embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
      embed.set_footer(text="Income accumulates up to 24h. Collect regularly for XP & reputation!")
      await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
  await bot.add_cog(BusinessCog(bot))
