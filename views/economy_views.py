import discord

from database import eco_col
from utils.economy import get_user_data, to_decimal128


class SellSelect(discord.ui.Select):
    def __init__(self, ctx, inventory):
        self.ctx = ctx
        self.inventory = inventory

        rarity_emojis = {
            "common": "⚪",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡",
            "godly": "🌌",
        }
        options = [
            discord.SelectOption(label="💰 Sell All Items", value="all", description="Liquidate your entire inventory")
        ]
        
        for index, item in enumerate(inventory[:24]):
            rarity = item.get("rarity", "common")
            options.append(
                discord.SelectOption(
                    label=item["name"][:100],
                    description=f"{rarity.capitalize()} • 🪙 {item['value']:,}",
                    emoji=rarity_emojis.get(rarity, "⚪"),
                    value=str(index),
                )
            )

        super().__init__(
            placeholder="Choose an item to sell...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ This menu is not for you.", ephemeral=True)

        user_id = str(self.ctx.author.id)
        user_data = get_user_data(user_id)
        inventory = user_data.get("inventory", [])

        from utils.economy import apply_amortization
        if self.values[0] == "all":
            if not inventory:
                return await interaction.response.send_message("❌ Your inventory is empty.", ephemeral=True)
                
            total_value = sum(item["value"] for item in inventory)
            actual_value = apply_amortization(user_id, total_value)
            eco_col.update_one(
                {"_id": user_id},
                {"$inc": {"wallet": to_decimal128(actual_value)}, "$set": {"inventory": []}},
            )
            embed = discord.Embed(title="💰 All Items Sold", color=0x2ECC71)
            desc = f"Sold **{len(inventory)}** items\n\nTotal Earned: 🪙 **{total_value:,}**"
            if actual_value < total_value:
                desc += f"\n📉 🪙 {total_value - actual_value:,} used to pay debt."
            embed.description = desc
            return await interaction.response.edit_message(content=None, embed=embed, view=None)

        selected_index = int(self.values[0])
        if selected_index >= len(inventory):
            return await interaction.response.send_message("❌ Item no longer exists.", ephemeral=True)

        item = inventory[selected_index]
        inventory.pop(selected_index)
        
        total_value = item["value"]
        actual_value = apply_amortization(user_id, total_value)

        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": to_decimal128(actual_value)}, "$set": {"inventory": inventory}},
        )

        embed = discord.Embed(title="💰 Item Sold", color=0x2ECC71)
        desc = f"Sold {item['name']}\n\nEarned: 🪙 **{total_value:,}**"
        if actual_value < total_value:
            desc += f"\n📉 🪙 {total_value - actual_value:,} used to pay debt."
        embed.description = desc
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class SellView(discord.ui.View):
    def __init__(self, ctx, inventory):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.inventory = inventory
        self.message: discord.Message | None = None
        self.add_item(SellSelect(ctx, inventory))

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(content="⏰ This menu expired.", view=None, embed=None)
            except Exception:
                pass
