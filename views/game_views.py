import random
import secrets

import discord

from utils.economy import update_wallet


class BlackjackView(discord.ui.View):
    def __init__(self, ctx, bet: int):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.bet = bet
        self.deck = self._create_deck()
        self.player_hand = [self._draw_card(), self._draw_card()]
        self.dealer_hand = [self._draw_card(), self._draw_card()]
        self.finished = False

    def _create_deck(self) -> list:
        suits = ['♠️', '♥️', '♦️', '♣️']
        values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [{'val': v, 'suit': s} for v in values for s in suits]
        secrets.SystemRandom().shuffle(deck)
        return deck

    def _draw_card(self) -> dict:
        return self.deck.pop()

    def _draw_player_card(self) -> dict:
        return self._draw_card()

    def _calculate_score(self, hand: list) -> int:
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

    def _format_hand(self, hand: list, hide_first: bool = False) -> str:
        if hide_first:
            return f"❓, {hand[1]['val']}{hand[1]['suit']}"
        return ", ".join(f"{c['val']}{c['suit']}" for c in hand)

    def create_embed(self, status: str = "Playing...") -> discord.Embed:
        p_score = self._calculate_score(self.player_hand)
        d_score = self._calculate_score(self.dealer_hand) if self.finished else "?"
        embed = discord.Embed(title="🃏 Blackjack Table", color=0x2B2D31)
        embed.add_field(name=f"Your Hand ({p_score})", value=self._format_hand(self.player_hand), inline=True)
        embed.add_field(
            name=f"Dealer Hand ({d_score})",
            value=self._format_hand(self.dealer_hand, not self.finished),
            inline=True,
        )
        embed.set_footer(text=f"Bet: 🪙 {self.bet} | Status: {status}")
        return embed

    async def _check_winner(self, interaction: discord.Interaction, stand: bool = False) -> None:
        p_score = self._calculate_score(self.player_hand)
        d_score = self._calculate_score(self.dealer_hand)

        if len(self.player_hand) == 2 and p_score == 21:
            if len(self.dealer_hand) == 2 and d_score == 21:
                return await self._end_game(interaction, "Both have Blackjack! It's a draw!", 0)
            return await self._end_game(interaction, "Blackjack! You win!", int(self.bet * 1.5))

        if p_score > 21:
            return await self._end_game(interaction, "You busted! Dealer wins.", -self.bet)

        if stand:
            while self._calculate_score(self.dealer_hand) < 17:
                self.dealer_hand.append(self._draw_card())

            d_score = self._calculate_score(self.dealer_hand)
            if d_score > 21:
                return await self._end_game(interaction, "Dealer busted! You win!", self.bet)
            elif p_score > d_score:
                return await self._end_game(interaction, "You win!", self.bet)
            elif p_score < d_score:
                return await self._end_game(interaction, "Dealer wins.", -self.bet)
            else:
                return await self._end_game(interaction, "It's a draw!", 0)

    async def _end_game(self, interaction: discord.Interaction, result_text: str, win_amount: int) -> None:
        self.finished = True
        self.hit_button.disabled = True
        self.stand_button.disabled = True
        user_id = str(self.ctx.author.id)
        
        if win_amount > 0:
            from utils.economy import apply_amortization
            actual_win = apply_amortization(user_id, win_amount)
            update_wallet(user_id, actual_win)
            
            # Bounty Tracking
            from utils.bounties import track_bounty_progress
            # For GAMBLER bounty, we track the profit (win_amount - bet is not correct here as win_amount is already the profit/payout)
            # In Blackjack, win_amount is the profit (bet*1 or bet*1.5)
            await track_bounty_progress(self.ctx.bot, user_id, "GAMBLER", win_amount)
            await track_bounty_progress(self.ctx.bot, user_id, "STREAK_GAMBLER", 1)
            
            if actual_win < win_amount:
                result_text += f"\n📉 🪙 {win_amount - actual_win:,} used to pay debt."
        elif win_amount < 0:
            update_wallet(user_id, win_amount)
            
        embed = self.create_embed(result_text)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(self._draw_player_card())
        if self._calculate_score(self.player_hand) >= 21:
            await self._check_winner(interaction, stand=True)
        else:
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._check_winner(interaction, stand=True)


class RPSView(discord.ui.View):
    def __init__(self, player: discord.Member):
        super().__init__(timeout=60)
        self.player = player

    async def _handle_choice(self, interaction: discord.Interaction, user_choice: str) -> None:
        if interaction.user != self.player:
            return await interaction.response.send_message(
                "❌ This is not your game! Start your own with /rps", ephemeral=True
            )

        choices = ["rock", "paper", "scissors"]
        bot_choice = random.choice(choices)
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

        if user_choice == bot_choice:
            result = "It's a tie! 🤝"
            color = 0xFFFF00
        elif (
            (user_choice == "rock" and bot_choice == "scissors")
            or (user_choice == "paper" and bot_choice == "rock")
            or (user_choice == "scissors" and bot_choice == "paper")
        ):
            result = "You win! 🎉"
            color = 0x00FF00
        else:
            result = "I win! 🤖"
            color = 0xFF0000

        embed = discord.Embed(title="Rock, Paper, Scissors", color=color)
        embed.add_field(name="You chose", value=f"{emojis[user_choice]} **{user_choice.capitalize()}**", inline=True)
        embed.add_field(name="I chose", value=f"{emojis[bot_choice]} **{bot_choice.capitalize()}**", inline=True)
        embed.add_field(name="Result", value=result, inline=False)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.blurple)
    async def rock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.gray)
    async def paper_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.red)
    async def scissors_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "scissors")
