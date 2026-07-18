import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("weekly-xp-bot")

DEFAULT_WEEKLY_XP_REQUIREMENT = 30_000
WEEKLY_XP_REQUIREMENT = int(os.getenv("WEEKLY_XP_REQUIREMENT", str(DEFAULT_WEEKLY_XP_REQUIREMENT)))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

WELCOME_CHANNEL_ID = 1513634912861950093
RULES_CHANNEL_ID = 1512990947187622060
JOIN_APPLY_CHANNEL_ID = 1515467362097434715
OWNER_IDS = {1436417791615045785, 941697213447421952, 1373879454077685800, 789938929151377428, 1325376607577178123}

# ── Modmail ──────────────────────────────────────────────────────────────────
# Dedicated staff server where DMs sent to the bot get relayed as channels
# inside a specific category.
MODMAIL_GUILD_ID = 1526562448872701962
# Category where new modmail ticket channels are created.
MODMAIL_CATEGORY_ID = 1526562449409441822
MODMAIL_MOD_ROLE_ID = 1526574388906823831
# Channel where a full HTML transcript + summary embed is posted once a modmail ticket is closed.
MODMAIL_TRANSCRIPT_CHANNEL_ID = 1526926325695250523

# ── Server boosts ────────────────────────────────────────────────────────────
# Channel where a thank-you message is posted whenever a member boosts the server.
BOOST_THANKS_CHANNEL_ID = 1524353296704340048

# Users allowed to use the !impostor command specifically (in addition to OWNER_IDS)
IMPOSTOR_ALLOWED_IDS = {941697213447421952, 1373879454077685800, 789938929151377428}

# Users allowed to use the !add command specifically (in addition to the owner)
ADD_ALLOWED_IDS = {789938929151377428}

# Coins are stored as BSON Decimal128 (not a plain 8-byte Mongo int), which
# supports values up to roughly 10^6144 — practically unlimited for a game
# economy. This cap is just a sanity guard against typos/absurd inputs, not
# a storage limit.
MAX_ECONOMY_AMOUNT = 1_000_000_000_000_000_000_000_000_000_000  # 1 nonillion

# ── Horse race (multiplayer betting) ────────────────────────────────────────
# Horses are named after their color, matching HORSE_COLORS 1-to-1.
HORSE_NAMES = ["Red", "Blue", "Green", "Yellow", "Purple"]
HORSE_COLORS = [
    (231, 76, 60),   # red
    (52, 152, 219),  # blue
    (46, 204, 113),  # green
    (241, 196, 15),  # yellow
    (155, 89, 182),  # purple
]
HORSERACE_BETTING_SECONDS = 45
HORSERACE_MIN_BETTORS = 2
HORSERACE_DISTANCE = 220

ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
VALID_BETS = {"red", "black", "even", "odd", "specific_number", "1st", "2nd", "3rd"}

CARD_EMOJIS = {
    '♠️': {'2': '🂢', '3': '🂣', '4': '🂤', '5': '🂥', '6': '🂦', '7': '🂧', '8': '🂨', '9': '🂩', '10': '🂪', 'J': '🂫', 'Q': '🂭', 'K': '🂮', 'A': '🂡'},
    '♥️': {'2': '🂲', '3': '🂳', '4': '🂴', '5': '🂵', '6': '🂶', '7': '🂷', '8': '🂸', '9': '🂹', '10': '🂺', 'J': '🂻', 'Q': '🂽', 'K': '🂾', 'A': '🂱'},
    '♦️': {'2': '🃂', '3': '🃃', '4': '🃄', '5': '🃅', '6': '🃆', '7': '🃇', '8': '🃈', '9': '🃉', '10': '🃊', 'J': '🃋', 'Q': '🃍', 'K': '🃎', 'A': '🃁'},
    '♣️': {'2': '🃒', '3': '🃓', '4': '🃔', '5': '🃕', '6': '🃖', '7': '🃗', '8': '🃘', '9': '🃙', '10': '🃚', 'J': '🃛', 'Q': '🃝', 'K': '🃞', 'A': '🃑'},
}
CARD_BACK = "🂠"


PET_LOOT_PROBABILITIES = {
    "slime":    {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "rabbit":   {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "mouse":    {"common": 92, "rare": 6, "epic": 1.5, "legendary": 0.5},
    "bat":      {"common": 88, "rare": 10, "epic": 1.5, "legendary": 0.5},
    "spider":   {"common": 86, "rare": 12, "epic": 1.5, "legendary": 0.5},
    "snake":    {"common": 85, "rare": 12, "epic": 2.5, "legendary": 0.5},
    "frog":     {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "turtle":   {"common": 85, "rare": 12, "epic": 2.5, "legendary": 0.5},
    "parrot":   {"common": 84, "rare": 13, "epic": 2.5, "legendary": 0.5},
    "penguin":  {"common": 83, "rare": 14, "epic": 2.5, "legendary": 0.5},
    "raccoon":  {"common": 82, "rare": 15, "epic": 2.5, "legendary": 0.5},
    "dog":      {"common": 83, "rare": 14, "epic": 2.5, "legendary": 0.5},
    "cat":      {"common": 80, "rare": 17, "epic": 2.5, "legendary": 0.5},
    "owl":      {"common": 78, "rare": 18, "epic": 3.5, "legendary": 0.5},
    "fox":      {"common": 75, "rare": 20, "epic": 4.5, "legendary": 0.5},
    "wolf":     {"common": 70, "rare": 24, "epic": 5,   "legendary": 1},
    "tiger":    {"common": 65, "rare": 28, "epic": 6,   "legendary": 1},
    "bear":     {"common": 63, "rare": 30, "epic": 6,   "legendary": 1},
    "griffin":  {"common": 60, "rare": 31, "epic": 8,   "legendary": 1},
    "lynx":     {"common": 70, "rare": 24, "epic": 5,   "legendary": 1},
    "panther":  {"common": 70, "rare": 24, "epic": 5,   "legendary": 1},
    "rhino":    {"common": 68, "rare": 25, "epic": 6,   "legendary": 1},
    "elephant": {"common": 68, "rare": 25, "epic": 6,   "legendary": 1},
    "shark":    {"common": 65, "rare": 28, "epic": 6,   "legendary": 1},
    "eagle":    {"common": 65, "rare": 28, "epic": 6,   "legendary": 1},
    "cobra":    {"common": 62, "rare": 30, "epic": 7,   "legendary": 1},
    "hyena":    {"common": 62, "rare": 30, "epic": 7,   "legendary": 1},
    "cheetah":  {"common": 60, "rare": 31, "epic": 8,   "legendary": 1},
    "gorilla":  {"common": 60, "rare": 31, "epic": 8,   "legendary": 1},
    "dragon":      {"common": 55, "rare": 30, "epic": 13,  "legendary": 2},
    "golem":       {"common": 52, "rare": 32, "epic": 14,  "legendary": 2},
    "hydra":       {"common": 50, "rare": 32, "epic": 15,  "legendary": 3},
    "pegasus":     {"common": 45, "rare": 35, "epic": 16,  "legendary": 4},
    "unicorn":     {"common": 55, "rare": 30, "epic": 13,  "legendary": 2},
    "manticore":   {"common": 55, "rare": 30, "epic": 13,  "legendary": 2},
    "basilisk":    {"common": 52, "rare": 32, "epic": 14,  "legendary": 2},
    "cerberus":    {"common": 52, "rare": 32, "epic": 14,  "legendary": 2},
    "thunderbird": {"common": 50, "rare": 32, "epic": 15,  "legendary": 3},
    "yeti":        {"common": 50, "rare": 32, "epic": 15,  "legendary": 3},
    "wyvern":      {"common": 48, "rare": 33, "epic": 16,  "legendary": 3},
    "ent":         {"common": 48, "rare": 33, "epic": 16,  "legendary": 3},
    "minotaur":    {"common": 45, "rare": 35, "epic": 16,  "legendary": 4},
    "golem_core":  {"common": 45, "rare": 35, "epic": 16,  "legendary": 4},
    "phoenix":      {"common": 35, "rare": 35, "epic": 25, "legendary": 4.5, "godly": 0.5},
    "chimera":      {"common": 33, "rare": 34, "epic": 27, "legendary": 5.5, "godly": 0.5},
    "kraken":       {"common": 30, "rare": 33, "epic": 30, "legendary": 6,   "godly": 1},
    "leviathan":    {"common": 27, "rare": 30, "epic": 34, "legendary": 8,   "godly": 1},
    "titan":        {"common": 25, "rare": 25, "epic": 37, "legendary": 11,  "godly": 2},
    "bahamut":      {"common": 20, "rare": 20, "epic": 44, "legendary": 14,  "godly": 2},
    "cthulhu":      {"common": 15, "rare": 15, "epic": 47, "legendary": 20,  "godly": 3},
    "reaper":       {"common": 15, "rare": 15, "epic": 47, "legendary": 20,  "godly": 3},
    "archangel":    {"common": 10, "rare": 10, "epic": 50, "legendary": 26,  "godly": 4},
    "demon_lord":   {"common": 10, "rare": 10, "epic": 50, "legendary": 26,  "godly": 4},
    "void_dragon":  {"common": 5,  "rare": 5,  "epic": 45, "legendary": 40,  "godly": 5},
}

PET_SHOP = {
    "slime":    {"price": 5_000,       "hp": 50,   "damage": 10,  "emoji": "🧪"},
    "rabbit":   {"price": 3_500,       "hp": 40,   "damage": 8,   "emoji": "🐇"},
    "mouse":    {"price": 2_500,       "hp": 30,   "damage": 12,  "emoji": "🐭"},
    "bat":      {"price": 6_000,       "hp": 45,   "damage": 15,  "emoji": "🦇"},
    "spider":   {"price": 7_500,       "hp": 35,   "damage": 22,  "emoji": "🕷️"},
    "snake":    {"price": 9_000,       "hp": 60,   "damage": 18,  "emoji": "🐍"},
    "frog":     {"price": 4_500,       "hp": 55,   "damage": 10,  "emoji": "🐸"},
    "turtle":   {"price": 10_000,      "hp": 120,  "damage": 5,   "emoji": "🐢"},
    "parrot":   {"price": 8_000,       "hp": 50,   "damage": 20,  "emoji": "🦜"},
    "penguin":  {"price": 11_000,      "hp": 70,   "damage": 15,  "emoji": "🐧"},
    "raccoon":  {"price": 13_000,      "hp": 65,   "damage": 25,  "emoji": "🦝"},
    "dog":      {"price": 12_000,      "hp": 100,  "damage": 20,  "emoji": "🐕"},
    "cat":      {"price": 15_000,      "hp": 80,   "damage": 25,  "emoji": "🐈"},
    "owl":      {"price": 25_000,      "hp": 90,   "damage": 30,  "emoji": "🦉"},
    "fox":      {"price": 40_000,      "hp": 110,  "damage": 35,  "emoji": "🦊"},
    "lynx":     {"price": 35_000,      "hp": 100,  "damage": 45,  "emoji": "🐆"},
    "panther":  {"price": 45_000,      "hp": 120,  "damage": 55,  "emoji": "🐈‍⬛"},
    "rhino":    {"price": 65_000,      "hp": 200,  "damage": 30,  "emoji": "🦏"},
    "elephant": {"price": 80_000,      "hp": 250,  "damage": 35,  "emoji": "🐘"},
    "shark":    {"price": 55_000,      "hp": 130,  "damage": 60,  "emoji": "🦈"},
    "eagle":    {"price": 40_000,      "hp": 90,   "damage": 50,  "emoji": "🦅"},
    "cobra":    {"price": 30_000,      "hp": 80,   "damage": 65,  "emoji": "🐍"},
    "hyena":    {"price": 28_000,      "hp": 110,  "damage": 40,  "emoji": "🐕"},
    "cheetah":  {"price": 50_000,      "hp": 85,   "damage": 75,  "emoji": "🐆"},
    "gorilla":  {"price": 70_000,      "hp": 180,  "damage": 45,  "emoji": "🦍"},
    "wolf":     {"price": 85_000,      "hp": 150,  "damage": 40,  "emoji": "🐺"},
    "tiger":    {"price": 150_000,     "hp": 220,  "damage": 80,  "emoji": "🐯"},
    "bear":     {"price": 225_000,     "hp": 300,  "damage": 60,  "emoji": "🐻"},
    "griffin":  {"price": 500_000,     "hp": 450,  "damage": 120, "emoji": "🦅"},
    "unicorn":  {"price": 180_000,     "hp": 200,  "damage": 100, "emoji": "🦄"},
    "manticore":{"price": 250_000,     "hp": 280,  "damage": 110, "emoji": "🦁"},
    "basilisk": {"price": 350_000,     "hp": 350,  "damage": 130, "emoji": "🦎"},
    "cerberus": {"price": 500_000,     "hp": 500,  "damage": 140, "emoji": "🐕"},
    "thunderbird":{"price": 750_000,   "hp": 400,  "damage": 250, "emoji": "⚡"},
    "yeti":     {"price": 450_000,     "hp": 600,  "damage": 90,  "emoji": "🧊"},
    "wyvern":   {"price": 850_000,     "hp": 450,  "damage": 220, "emoji": "🐲"},
    "ent":      {"price": 400_000,     "hp": 800,  "damage": 70,  "emoji": "🌳"},
    "minotaur": {"price": 300_000,     "hp": 420,  "damage": 140, "emoji": "🐂"},
    "golem_core":{"price": 600_000,    "hp": 750,  "damage": 110, "emoji": "💠"},
    "dragon":   {"price": 1_200_000,   "hp": 1000, "damage": 300, "emoji": "🐉"},
    "golem":    {"price": 2_500_000,   "hp": 2000, "damage": 250, "emoji": "🗿"},
    "hydra":    {"price": 5_000_000,   "hp": 3000, "damage": 400, "emoji": "🐍"},
    "pegasus":  {"price": 8_500_000,   "hp": 4500, "damage": 550, "emoji": "🦄"},
    "phoenix":  {"price": 15_000_000,  "hp": 6000, "damage": 800, "emoji": "🐦‍🔥"},
    "chimera":  {"price": 25_000_000,  "hp": 8000, "damage": 1000, "emoji": "🦁"},
    "kraken":   {"price": 50_000_000,  "hp": 12000, "damage": 1500, "emoji": "🦑"},
    "leviathan":{"price": 100_000_000, "hp": 20000, "damage": 2500, "emoji": "🌊"},
    "titan":    {"price": 250_000_000, "hp": 40000, "damage": 4500, "emoji": "👑"},
    "bahamut":  {"price": 500_000_000, "hp": 75000, "damage": 8000, "emoji": "🌌"},
    "cthulhu":  {"price": 15_000_000_000, "hp": 250_000, "damage": 25_000, "emoji": "🐙"},
    "reaper":   {"price": 12_000_000_000, "hp": 180_000, "damage": 35_000, "emoji": "💀"},
    "archangel":{"price": 25_000_000_000, "hp": 500_000, "damage": 45_000, "emoji": "😇"},
    "demon_lord":{"price": 20_000_000_000, "hp": 400_000, "damage": 55_000, "emoji": "😈"},
    "void_dragon":{"price": 75_000_000_000, "hp": 1_500_000, "damage": 150_000, "emoji": "🌌"},
}

FOOD_ITEMS = {
    "basic": {"price": 25_000, "hunger": 20, "emoji": "🍖", "name": "Basic Food"},
    "premium": {"price": 100_000, "hunger": 50, "emoji": "🥩", "name": "Premium Food"},
    "enchanted": {"price": 500_000, "hunger": 100, "emoji": "🍱", "name": "Enchanted Food"},
}

ROLE_SHOP = {
    "bronze":    {"price": 25_000,        "claim": 2_000,       "role_id": 1523427695638085643},
    "silver":    {"price": 75_000,        "claim": 5_000,       "role_id": 1523427696284270715},
    "gold":      {"price": 200_000,       "claim": 12_000,      "role_id": 1523427697198497963},
    "diamond":   {"price": 500_000,       "claim": 30_000,      "role_id": 1523427697966190642},
    "emerald":   {"price": 1_000_000,     "claim": 75_000,      "role_id": 1523427698452463767},
    "mythic":    {"price": 3_000_000,     "claim": 200_000,     "role_id": 1523427698981077023},
    "cosmic":    {"price": 10_000_000,    "claim": 650_000,     "role_id": 1523427699442450675},
    "eternal":   {"price": 25_000_000,    "claim": 1_500_000,   "role_id": 1523427700079988816},
    "secret":    {"price": 75_000_000,    "claim": 4_000_000,   "role_id": 1523427700755136712},
    "godlike":   {"price": 200_000_000,   "claim": 10_000_000,  "role_id": 1523427701363441784},
    "celestial": {"price": 500_000_000,   "claim": 25_000_000,  "role_id": 1523427702252765377},
    "ascended":  {"price": 1_000_000_000, "claim": 60_000_000,  "role_id": 1523427702797893764},
}

PET_RARITIES = {
    "slime": "basic", "rabbit": "basic", "mouse": "basic", "bat": "basic", "spider": "basic",
    "snake": "basic", "frog": "basic", "turtle": "basic", "parrot": "basic", "penguin": "basic",
    "raccoon": "basic", "dog": "basic", "cat": "basic", "owl": "basic", "fox": "basic",
    "wolf": "rare", "tiger": "rare", "bear": "rare", "griffin": "rare", "lynx": "rare",
    "panther": "rare", "rhino": "rare", "elephant": "rare", "shark": "rare", "eagle": "rare",
    "cobra": "rare", "hyena": "rare", "cheetah": "rare", "gorilla": "rare",
    "dragon": "epic", "golem": "epic", "hydra": "epic", "pegasus": "epic", "unicorn": "epic",
    "manticore": "epic", "basilisk": "epic", "cerberus": "epic", "thunderbird": "epic", "yeti": "epic",
    "wyvern": "epic", "ent": "epic", "minotaur": "epic", "golem_core": "epic",
    "phoenix": "legendary", "chimera": "legendary", "kraken": "legendary",
    "leviathan": "legendary", "titan": "legendary", "bahamut": "legendary",
    "cthulhu": "legendary", "reaper": "legendary", "archangel": "legendary",
    "demon_lord": "legendary", "void_dragon": "legendary",
}

ADVENTURE_LOOT = {
    "common": [
        ("🪵 Stick", 8), ("🪨 Rock", 10), ("🔩 Screw", 12), ("🧻 Old Cloth", 9),
        ("🥫 Rusty Can", 11), ("🪢 Rope", 15), ("🧴 Plastic Bottle", 6),
        ("📎 Metal Scrap", 18), ("🪛 Broken Tool", 20), ("🪙 Small Coin", 25),
        ("🔋 Dead Battery", 14), ("📦 Wooden Crate", 22), ("🕯️ Candle", 10),
        ("🧱 Brick", 13), ("⚙️ Gear", 28), ("🪓 Rusty Axe", 30),
        ("🪤 Bear Trap", 38), ("📜 Torn Map", 40), ("🥄 Silver Spoon", 48),
        ("🧲 Magnet", 20), ("🧃 Juice Box", 8), ("🪙 Copper Coin", 18),
        ("🎣 Fishing Hook", 22), ("📻 Broken Radio", 45), ("⌚ Old Watch", 55),
        ("🧤 Leather Glove", 25), ("🪖 Cracked Helmet", 60), ("🗝️ Tiny Key", 70),
        ("🪞 Shattered Mirror", 38), ("🥾 Old Boot", 5), ("🔩 Rusty Nail", 6),
        ("🥄 Plastic Spoon", 4), ("📦 Cardboard Box", 8), ("🍾 Empty Bottle", 3),
        ("🩹 Used Bandage", 10), ("🦴 Fish Bone", 7), ("📰 Soggy Newspaper", 9),
        ("🧦 Dirty Sock", 6), ("🖇️ Bent Paperclip", 4), ("💎 Glass Shard", 11),
        ("🔪 Dull Knife", 13), ("🧵 Frayed String", 7), ("🔮 Chipped Marble", 8),
        ("🔥 Burnt Match", 2), ("🪵 Twig", 3), ("🪨 Gravel", 4), ("🔩 Nut", 5),
    ],
    "rare": [
        ("💍 Silver Ring", 200), ("🪙 Gold Coin", 300), ("💎 Sapphire", 480),
        ("🔮 Magic Orb", 600), ("📿 Ancient Necklace", 720), ("⚔️ Knight Dagger", 880),
        ("🏺 Ancient Vase", 1000), ("💠 Emerald", 1200), ("🧪 Rare Potion", 1400),
        ("📦 Treasure Chest", 1600), ("🗡️ Assassin Blade", 1680), ("🛡️ Golden Shield", 2000),
        ("💰 Hidden Stash", 2200), ("📜 Enchanted Scroll", 2400), ("🪬 Lucky Charm", 2600),
        ("🧿 Mystic Eye", 2800), ("🐚 Pearl Shell", 3000), ("💎 Ruby Crystal", 3200),
        ("⚡ Charged Core", 3400), ("🔑 Ancient Key", 3600), ("🪨 Polished Pebble", 180),
        ("🪙 Silver Coin", 240), ("🗝️ Iron Key", 340), ("🥉 Bronze Medal", 280),
    ],
    "epic": [
        ("👑 Golden Crown", 5000), ("💎 Large Diamond", 7500), ("🏺 Cursed Idol", 9000),
        ("🔮 Dragon Eye", 12000), ("⚔️ Holy Excalibur", 15000), ("🧬 Alien Tech", 18000),
        ("💠 Pure Essence", 20000), ("🧪 Elixir of Life", 25000), ("📜 Lost Prophecy", 30000),
        ("📦 Celestial Crate", 40000), ("💍 Phoenix Ring", 50000), ("🛡️ Dragon Scale Shield", 60000),
    ],
    "legendary": [
        ("🌌 Void Core", 150000), ("⭐ Fallen Star", 250000), ("🏺 Pandora's Box", 500000),
        ("🔮 Eye of Eternity", 750000), ("⚔️ God Slayer", 1000000), ("🧬 Genesis Code", 1500000),
    ],
    "godly": [
        ("♾️ Infinity Stone", 10_000_000), ("🌌 Universe Fragment", 25_000_000), ("👑 Crown of Creation", 50_000_000),
    ]
}

PRESTIGE_LEVELS = {
    0: {"name": "None", "threshold": 0, "discount": 0.0, "loan_mult": 1.0},
    1: {"name": "Bronze", "threshold": 100_000, "discount": 0.02, "loan_mult": 1.0},
    2: {"name": "Silver", "threshold": 500_000, "discount": 0.05, "loan_mult": 2.0},
    3: {"name": "Gold", "threshold": 2_000_000, "discount": 0.08, "loan_mult": 5.0},
    4: {"name": "Platinum", "threshold": 10_000_000, "discount": 0.12, "loan_mult": 10.0},
    5: {"name": "Emerald", "threshold": 50_000_000, "discount": 0.15, "loan_mult": 20.0},
    6: {"name": "Diamond", "threshold": 200_000_000, "discount": 0.20, "loan_mult": 50.0},
    7: {"name": "Master", "threshold": 1_000_000_000, "discount": 0.25, "loan_mult": 100.0},
}

BREEDING_COST_RATIO = 0.25
BREEDING_SUCCESS_CHANCE = 70
BREEDING_RISK_CHANCE = 5

STOCK_SYMBOLS = {
    "VRTX": {"name": "Vertex Dynamics", "sector": "AI & Robotics", "volatility": 0.05, "initial_price": 500, "description": "Cutting-edge AI and robotics solutions."},
    "GLBL": {"name": "Global Energy", "sector": "Energy", "volatility": 0.02, "initial_price": 500, "description": "Sustainable energy and infrastructure."},
    "AURA": {"name": "Aura Pharmaceuticals", "sector": "Biotech", "volatility": 0.04, "initial_price": 500, "description": "Next-gen medical research and biotech."},
    "ORBT": {"name": "Orbital Space", "sector": "Space Tourism", "volatility": 0.08, "initial_price": 500, "description": "Commercial space travel and tourism."},
    "TITN": {"name": "Titan Heavy Industries", "sector": "Manufacturing", "volatility": 0.03, "initial_price": 500, "description": "Heavy machinery and industrial production."},
}

STOCK_UPDATE_INTERVAL = 30
STOCK_HISTORY_LIMIT = 96
STOCK_FEE = 0.02
STOCK_DIVIDEND_RATE = 0.005
STOCK_NEWS_PROBABILITY = 0.30
STOCK_NEWS_CHANNEL_ID = 1206197908399980575

ADVENTURE_EVENTS = [
    {"text": "Your pet found a small hidden stash!", "min_gain": 50, "max_gain": 200},
    {"text": "Your pet helped a traveler and received a tip.", "min_gain": 30, "max_gain": 150},
    {"text": "Your pet discovered a pile of shiny coins in a cave.", "min_gain": 100, "max_gain": 500},
    {"text": "Your pet won a local race!", "min_gain": 200, "max_gain": 800},
    {"text": "Your pet found some loose change on the street.", "min_gain": 10, "max_gain": 50},
    {"text": "Your pet dug up a small treasure chest.", "min_gain": 500, "max_gain": 1500},
    {"text": "Your pet found a lost wallet and kept the reward.", "min_gain": 150, "max_gain": 400},
    {"text": "Your pet scavenged through some ruins.", "min_gain": 80, "max_gain": 300},
    {"text": "Your pet performed tricks for a crowd.", "min_gain": 120, "max_gain": 350},
    {"text": "Your pet found a rare gem and sold it.", "min_gain": 1000, "max_gain": 3000},
]

STOCKS = {
    "VRTX": {"name": "Vertex Dynamics", "sector": "AI & Robotics", "volatility": 0.12, "initial_price": 500, "description": "Cutting-edge AI and robotics solutions."},
    "CRPT": {"name": "CryptoVault Financial", "sector": "Finance", "volatility": 0.20, "initial_price": 450, "description": "Decentralized finance and digital asset management."},
    "AURA": {"name": "Aura Pharmaceuticals", "sector": "Biotech", "volatility": 0.10, "initial_price": 500, "description": "Next-gen medical research and biotech."},
    "ORBT": {"name": "Orbital Space", "sector": "Space Tourism", "volatility": 0.18, "initial_price": 500, "description": "Commercial space travel and tourism."},
    "TITN": {"name": "Titan Heavy Industries", "sector": "Manufacturing", "volatility": 0.08, "initial_price": 500, "description": "Heavy machinery and industrial production."},
}
