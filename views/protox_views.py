import discord

from utils.formatting import generate_top_clans_image


class TopClansPagination(discord.ui.View):
    def __init__(self, clans: list, page: int, per_page: int):
        super().__init__(timeout=120)
        self.clans = clans
        self.page = page
        self.per_page = per_page
        self.max_page = max(0, (len(clans) - 1) // per_page)
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.btn_prev.disabled = self.page == 0
        self.btn_next.disabled = self.page >= self.max_page

    async def _update_message(self, interaction: discord.Interaction) -> None:
        image_path = generate_top_clans_image(self.clans, self.page, self.per_page)
        file = discord.File(image_path, filename="top_clans.png")
        self._update_buttons()
        await interaction.response.edit_message(attachments=[file], view=self)

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.gray)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        await self._update_message(interaction)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.max_page, self.page + 1)
        await self._update_message(interaction)
