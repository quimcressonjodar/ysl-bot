import secrets

import discord

from utils.economy import update_wallet


def _create_deck() -> list:
    suits = ['♠️', '♥️', '♦️', '♣️']
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [{'val': v, 'suit': s} for v in values for s in suits]
    secrets.SystemRandom().shuffle(deck)
    return deck


def _calculate_score(hand: list) -> int:
    score = 0
    aces = 0
    values_map = {'J': 10, 'Q': 10, 'K': 10, 'A': 11}
    for card in hand:
        if card['val'].isdigit():
            score += int(card['val'])
        else:
            score += values_map[card['val']]
            if card['val'] == 'A':
                aces += 1
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    return score


def _format_hand(hand: list) -> str:
    return ", ".join(f"{c['val']}{c['suit']}" for c in hand)


class BlackjackChallengeView(discord.ui.View):
    """Sent to the challenged opponent — they must accept before the duel starts."""

    def __init__(self, challenger: discord.Member, opponent: discord.Member, bet: int):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.message: discord.Message | None = None
        self.responded = False

    async def on_timeout(self) -> None:
        if self.message and not self.responded:
            try:
                await self.message.edit(
                    content=f"⏰ {self.opponent.mention} no respondió al duelo a tiempo.", view=None
                )
            except Exception:
                pass

    @discord.ui.button(label="Aceptar duelo", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("❌ Este duelo no es para ti.", ephemeral=True)
        if self.responded:
            return await interaction.response.send_message("❌ Este duelo ya fue respondido.", ephemeral=True)

        from utils.economy import get_user_data
        challenger_data = get_user_data(str(self.challenger.id))
        opponent_data = get_user_data(str(self.opponent.id))

        if challenger_data["wallet"] < self.bet:
            self.responded = True
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"❌ {self.challenger.mention} ya no tiene suficientes monedas para el duelo.", view=self
            )
            return

        if opponent_data["wallet"] < self.bet:
            return await interaction.response.send_message(
                f"❌ No tienes suficientes monedas. Tu saldo es 🪙 {opponent_data['wallet']:,}.", ephemeral=True
            )

        self.responded = True
        update_wallet(str(self.challenger.id), -self.bet)
        update_wallet(str(self.opponent.id), -self.bet)

        for child in self.children:
            child.disabled = True

        game_view = BlackjackPvPView(self.challenger, self.opponent, self.bet)
        embed = game_view.create_embed(f"Turno de {self.challenger.display_name}")
        await interaction.response.edit_message(content=None, embed=embed, view=game_view)
        game_view.message = interaction.message

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("❌ Este duelo no es para ti.", ephemeral=True)
        if self.responded:
            return await interaction.response.send_message("❌ Este duelo ya fue respondido.", ephemeral=True)
        self.responded = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"🚫 {self.opponent.mention} rechazó el duelo de {self.challenger.mention}.", view=self
        )


class BlackjackPvPView(discord.ui.View):
    """Turn-based Blackjack between two human players (no dealer)."""

    def __init__(self, player_a: discord.Member, player_b: discord.Member, bet: int):
        super().__init__(timeout=120)
        self.players = [player_a, player_b]
        self.bet = bet
        self.deck = _create_deck()
        self.hands = {player_a.id: [self._draw(), self._draw()], player_b.id: [self._draw(), self._draw()]}
        self.standing: set[int] = set()
        self.busted: set[int] = set()
        self.turn = 0  # index into self.players
        self.finished = False
        self.message: discord.Message | None = None

    def _draw(self) -> dict:
        return self.deck.pop()

    async def on_timeout(self) -> None:
        if self.message and not self.finished:
            update_wallet(str(self.players[0].id), self.bet)
            update_wallet(str(self.players[1].id), self.bet)
            try:
                await self.message.edit(
                    content="⏰ Duelo cancelado por inactividad — apuestas reembolsadas.", view=None
                )
            except Exception:
                pass

    @property
    def current_player(self) -> discord.Member:
        return self.players[self.turn]

    def create_embed(self, status: str) -> discord.Embed:
        embed = discord.Embed(title="🃏 Blackjack PvP", color=0x2B2D31)
        for player in self.players:
            hand = self.hands[player.id]
            score = _calculate_score(hand)
            tag = ""
            if player.id in self.busted:
                tag = " 💥 Bust"
            elif player.id in self.standing:
                tag = " ✋ Plantado"
            embed.add_field(
                name=f"{player.display_name} ({score}){tag}",
                value=_format_hand(hand),
                inline=True,
            )
        embed.set_footer(text=f"Apuesta: 🪙 {self.bet} cada uno | {status}")
        return embed

    def _both_done(self) -> bool:
        for player in self.players:
            if player.id not in self.standing and player.id not in self.busted:
                return False
        return True

    async def _advance_or_finish(self, interaction: discord.Interaction):
        if self._both_done():
            await self._settle(interaction)
            return

        self.turn = 1 - self.turn
        # skip a player who is already standing/busted
        if self.current_player.id in self.standing or self.current_player.id in self.busted:
            self.turn = 1 - self.turn

        await interaction.response.edit_message(
            embed=self.create_embed(f"Turno de {self.current_player.display_name}"), view=self
        )

    async def _settle(self, interaction: discord.Interaction):
        self.finished = True
        for child in self.children:
            child.disabled = True

        a, b = self.players
        score_a = _calculate_score(self.hands[a.id])
        score_b = _calculate_score(self.hands[b.id])
        a_bust = a.id in self.busted
        b_bust = b.id in self.busted

        pot = self.bet * 2
        if a_bust and b_bust:
            result = "💥 ¡Ambos se pasaron de 21! Empate — apuestas devueltas."
            update_wallet(str(a.id), self.bet)
            update_wallet(str(b.id), self.bet)
        elif a_bust or (not b_bust and score_b > score_a):
            update_wallet(str(b.id), pot)
            result = f"🏆 {b.display_name} gana 🪙 {pot:,}"
        elif b_bust or (not a_bust and score_a > score_b):
            update_wallet(str(a.id), pot)
            result = f"🏆 {a.display_name} gana 🪙 {pot:,}"
        else:
            result = "🤝 Empate — apuestas devueltas."
            update_wallet(str(a.id), self.bet)
            update_wallet(str(b.id), self.bet)

        embed = self.create_embed(result)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_hit(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player.id:
            return await interaction.response.send_message("❌ No es tu turno.", ephemeral=True)

        player_id = interaction.user.id
        self.hands[player_id].append(self._draw())
        score = _calculate_score(self.hands[player_id])
        if score >= 21:
            if score > 21:
                self.busted.add(player_id)
            else:
                self.standing.add(player_id)
            await self._advance_or_finish(interaction)
        else:
            await interaction.response.edit_message(
                embed=self.create_embed(f"Turno de {self.current_player.display_name}"), view=self
            )

    async def _handle_stand(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player.id:
            return await interaction.response.send_message("❌ No es tu turno.", ephemeral=True)
        self.standing.add(interaction.user.id)
        await self._advance_or_finish(interaction)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_hit(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_stand(interaction)
