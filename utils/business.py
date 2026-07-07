"""
Business system — core logic and database operations.
Completely independent from the stock market system.
To add a new business type: add a key to BUSINESS_TYPES below.
"""
import random
import string
import time
from database import db

businesses_col = db["businesses"]

# ─────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────

COLLECTION_INTERVAL = 3600          # 1 hour in seconds
MAX_ACCUMULATION_HOURS = 24         # income cap

# XP required to reach next level (index = current level)
XP_PER_LEVEL = [0, 100, 250, 500, 900, 1_500, 2_500, 4_000, 6_500, 10_000]

# Income multiplier per level (index = level, max level 10)
LEVEL_INCOME_MULT = [1.0, 1.0, 1.15, 1.30, 1.50, 1.75, 2.10, 2.55, 3.10, 3.80, 4.60]

WORKER_NAMES = [
  "Alex", "Sam", "Jamie", "Jordan", "Taylor", "Morgan", "Casey", "Riley",
  "Quinn", "Avery", "Blake", "Drew", "Hayden", "Logan", "Peyton", "Reese",
  "Skyler", "Sage", "Charlie", "Frankie", "Dakota", "Emery", "Finley", "Harper",
  "Indigo", "Jules", "Kendall", "Lane", "Marlowe", "Nova", "Oakley", "Parker",
]


def reputation_multiplier(rep: int) -> float:
  """rep 0-100 -> income multiplier 0.5-1.5"""
  return 0.5 + (rep / 100.0)


# ─────────────────────────────────────────────────────────
# BUSINESS CATALOGUE
# To add a new type: copy any entry and customise it.
# ─────────────────────────────────────────────────────────
BUSINESS_TYPES: dict[str, dict] = {
  "restaurant": {
      "name": "Restaurant", "emoji": "\U0001f37d\ufe0f",
      "description": "A popular diner serving hungry customers day and night.",
      "base_cost": 50_000,
      "base_income_per_hour": 800,
      "base_maintenance_per_hour": 120,
      "max_workers": 8,
      "sell_multiplier": 0.60,
      "worker_roles": ["Chef", "Waiter", "Cashier", "Manager"],
      "worker_base_salary": 180,
      "upgrades": {
          "better_kitchen":  {"name": "Better Kitchen",  "emoji": "\U0001f373", "cost": 20_000,  "income_bonus": 0.15, "req_level": 1},
          "outdoor_seating": {"name": "Outdoor Seating", "emoji": "\U0001fa91", "cost": 35_000,  "income_bonus": 0.20, "req_level": 3},
          "vip_area":        {"name": "VIP Lounge",      "emoji": "\U0001f48e", "cost": 60_000,  "income_bonus": 0.25, "req_level": 5},
          "michelin_star":   {"name": "Michelin Star",   "emoji": "\u2b50",     "cost": 150_000, "income_bonus": 0.40, "req_level": 8},
      },
  },
  "cinema": {
      "name": "Cinema", "emoji": "\U0001f3ac",
      "description": "A movie theater with the latest blockbusters.",
      "base_cost": 75_000,
      "base_income_per_hour": 1_100,
      "base_maintenance_per_hour": 200,
      "max_workers": 6,
      "sell_multiplier": 0.60,
      "worker_roles": ["Projectionist", "Ticket Seller", "Usher", "Manager"],
      "worker_base_salary": 220,
      "upgrades": {
          "new_projectors": {"name": "New Projectors", "emoji": "\U0001f4fd\ufe0f", "cost": 30_000,  "income_bonus": 0.15, "req_level": 1},
          "vip_seats":      {"name": "VIP Seats",      "emoji": "\U0001f6cb\ufe0f","cost": 50_000,  "income_bonus": 0.20, "req_level": 3},
          "imax_screen":    {"name": "IMAX Screen",    "emoji": "\U0001f39e\ufe0f","cost": 100_000, "income_bonus": 0.35, "req_level": 6},
          "food_court":     {"name": "Food Court",     "emoji": "\U0001f37f",       "cost": 80_000,  "income_bonus": 0.25, "req_level": 5},
      },
  },
  "store": {
      "name": "Store", "emoji": "\U0001f3ea",
      "description": "A general merchandise shop on a busy street.",
      "base_cost": 30_000,
      "base_income_per_hour": 500,
      "base_maintenance_per_hour": 80,
      "max_workers": 5,
      "sell_multiplier": 0.60,
      "worker_roles": ["Cashier", "Stock Clerk", "Security", "Manager"],
      "worker_base_salary": 130,
      "upgrades": {
          "self_checkout":   {"name": "Self-Checkout",   "emoji": "\U0001f916",     "cost": 15_000,  "income_bonus": 0.15, "req_level": 1},
          "loyalty_program": {"name": "Loyalty Program", "emoji": "\U0001f3ab",     "cost": 25_000,  "income_bonus": 0.20, "req_level": 3},
          "second_floor":    {"name": "Second Floor",    "emoji": "\U0001f3d7\ufe0f","cost": 60_000, "income_bonus": 0.30, "req_level": 5},
          "brand_deal":      {"name": "Brand Deal",      "emoji": "\U0001f91d",     "cost": 100_000, "income_bonus": 0.35, "req_level": 8},
      },
  },
  "waterpark": {
      "name": "Water Park", "emoji": "\U0001f30a",
      "description": "A splashing good time for families and thrill-seekers.",
      "base_cost": 200_000,
      "base_income_per_hour": 2_500,
      "base_maintenance_per_hour": 600,
      "max_workers": 15,
      "sell_multiplier": 0.60,
      "worker_roles": ["Lifeguard", "Ride Operator", "Ticket Seller", "Janitor", "Manager"],
      "worker_base_salary": 280,
      "upgrades": {
          "wave_pool":    {"name": "Wave Pool",    "emoji": "\U0001f3c4",     "cost": 80_000,  "income_bonus": 0.20, "req_level": 2},
          "lazy_river":   {"name": "Lazy River",   "emoji": "\U0001f6f6",     "cost": 120_000, "income_bonus": 0.25, "req_level": 4},
          "speed_slides": {"name": "Speed Slides", "emoji": "\U0001f3a2",     "cost": 200_000, "income_bonus": 0.35, "req_level": 6},
          "vip_cabanas":  {"name": "VIP Cabanas",  "emoji": "\U0001f3d6\ufe0f","cost": 300_000,"income_bonus": 0.40, "req_level": 8},
      },
  },
  "museum": {
      "name": "Museum", "emoji": "\U0001f3db\ufe0f",
      "description": "A prestigious institution showcasing art and history.",
      "base_cost": 120_000,
      "base_income_per_hour": 1_400,
      "base_maintenance_per_hour": 300,
      "max_workers": 10,
      "sell_multiplier": 0.60,
      "worker_roles": ["Curator", "Guide", "Security Guard", "Restorer", "Manager"],
      "worker_base_salary": 250,
      "upgrades": {
          "digital_exhibits": {"name": "Digital Exhibits", "emoji": "\U0001f4f1",     "cost": 50_000,  "income_bonus": 0.20, "req_level": 2},
          "gift_shop":        {"name": "Gift Shop",        "emoji": "\U0001f381",     "cost": 30_000,  "income_bonus": 0.15, "req_level": 1},
          "night_tours":      {"name": "Night Tours",      "emoji": "\U0001f319",     "cost": 70_000,  "income_bonus": 0.25, "req_level": 5},
          "world_tour_art":   {"name": "World Tour Art",   "emoji": "\U0001f5bc\ufe0f","cost": 150_000,"income_bonus": 0.35, "req_level": 7},
      },
  },
  "hotel": {
      "name": "Hotel", "emoji": "\U0001f3e8",
      "description": "A luxurious stay for travelers from around the world.",
      "base_cost": 180_000,
      "base_income_per_hour": 2_200,
      "base_maintenance_per_hour": 500,
      "max_workers": 12,
      "sell_multiplier": 0.60,
      "worker_roles": ["Receptionist", "Housekeeper", "Bellhop", "Chef", "Manager"],
      "worker_base_salary": 270,
      "upgrades": {
          "spa":             {"name": "Spa & Wellness",  "emoji": "\U0001f9d6", "cost": 80_000,  "income_bonus": 0.20, "req_level": 2},
          "rooftop_pool":    {"name": "Rooftop Pool",    "emoji": "\U0001f3ca", "cost": 150_000, "income_bonus": 0.25, "req_level": 4},
          "conference_hall": {"name": "Conference Hall", "emoji": "\U0001f935", "cost": 100_000, "income_bonus": 0.20, "req_level": 3},
          "five_stars":      {"name": "5-Star Rating",   "emoji": "\u2b50",     "cost": 250_000, "income_bonus": 0.40, "req_level": 8},
      },
  },
  "gym": {
      "name": "Gym", "emoji": "\U0001f3cb\ufe0f",
      "description": "A state-of-the-art fitness center for peak performance.",
      "base_cost": 40_000,
      "base_income_per_hour": 600,
      "base_maintenance_per_hour": 100,
      "max_workers": 6,
      "sell_multiplier": 0.60,
      "worker_roles": ["Trainer", "Receptionist", "Cleaner", "Manager"],
      "worker_base_salary": 160,
      "upgrades": {
          "new_equipment":     {"name": "New Equipment",     "emoji": "\U0001f3c3",                       "cost": 20_000, "income_bonus": 0.20, "req_level": 1},
          "sauna":             {"name": "Sauna Room",         "emoji": "\u2668\ufe0f",                    "cost": 35_000, "income_bonus": 0.20, "req_level": 3},
          "juice_bar":         {"name": "Juice Bar",          "emoji": "\U0001f964",                       "cost": 25_000, "income_bonus": 0.15, "req_level": 2},
          "personal_training": {"name": "Personal Training",  "emoji": "\U0001f9d1\u200d\U0001f3eb",    "cost": 60_000, "income_bonus": 0.30, "req_level": 6},
      },
  },
  "cafe": {
      "name": "Caf\u00e9", "emoji": "\u2615",
      "description": "A charming coffee spot beloved by the morning crowd.",
      "base_cost": 25_000,
      "base_income_per_hour": 420,
      "base_maintenance_per_hour": 60,
      "max_workers": 4,
      "sell_multiplier": 0.60,
      "worker_roles": ["Barista", "Cashier", "Baker", "Manager"],
      "worker_base_salary": 110,
      "upgrades": {
          "espresso_machine": {"name": "Premium Espresso", "emoji": "\u2615",     "cost": 12_000, "income_bonus": 0.15, "req_level": 1},
          "coworking_space":  {"name": "Co-Working Space", "emoji": "\U0001f4bb", "cost": 20_000, "income_bonus": 0.20, "req_level": 2},
          "pastry_display":   {"name": "Pastry Display",   "emoji": "\U0001f950", "cost": 15_000, "income_bonus": 0.15, "req_level": 2},
          "franchise_deal":   {"name": "Franchise Deal",   "emoji": "\U0001f30d", "cost": 80_000, "income_bonus": 0.35, "req_level": 7},
      },
  },
  "bakery": {
      "name": "Bakery", "emoji": "\U0001f956",
      "description": "Fresh bread and pastries baked from scratch every morning.",
      "base_cost": 22_000,
      "base_income_per_hour": 380,
      "base_maintenance_per_hour": 55,
      "max_workers": 4,
      "sell_multiplier": 0.60,
      "worker_roles": ["Baker", "Cashier", "Delivery Driver", "Manager"],
      "worker_base_salary": 100,
      "upgrades": {
          "brick_oven":       {"name": "Brick Oven",       "emoji": "\U0001f525", "cost": 10_000, "income_bonus": 0.15, "req_level": 1},
          "custom_cakes":     {"name": "Custom Cakes",     "emoji": "\U0001f382", "cost": 18_000, "income_bonus": 0.20, "req_level": 2},
          "delivery_service": {"name": "Delivery Service", "emoji": "\U0001f6f5", "cost": 25_000, "income_bonus": 0.20, "req_level": 3},
          "artisan_brand":    {"name": "Artisan Brand",    "emoji": "\U0001f3c5", "cost": 70_000, "income_bonus": 0.35, "req_level": 7},
      },
  },
  "gasstation": {
      "name": "Gas Station", "emoji": "\u26fd",
      "description": "Fueling vehicles and travelers around the clock.",
      "base_cost": 60_000,
      "base_income_per_hour": 900,
      "base_maintenance_per_hour": 180,
      "max_workers": 5,
      "sell_multiplier": 0.60,
      "worker_roles": ["Attendant", "Cashier", "Mechanic", "Manager"],
      "worker_base_salary": 150,
      "upgrades": {
          "car_wash":          {"name": "Car Wash",         "emoji": "\U0001f697", "cost": 25_000,  "income_bonus": 0.20, "req_level": 1},
          "convenience_store": {"name": "Convenience Store","emoji": "\U0001f3ea", "cost": 40_000,  "income_bonus": 0.20, "req_level": 3},
          "ev_chargers":       {"name": "EV Chargers",      "emoji": "\u26a1",     "cost": 70_000,  "income_bonus": 0.25, "req_level": 5},
          "truck_stop":        {"name": "Truck Stop",       "emoji": "\U0001f69b", "cost": 120_000, "income_bonus": 0.30, "req_level": 7},
      },
  },
  "cardealership": {
      "name": "Car Dealership", "emoji": "\U0001f698",
      "description": "A glossy showroom moving luxury and everyday vehicles.",
      "base_cost": 150_000,
      "base_income_per_hour": 2_000,
      "base_maintenance_per_hour": 450,
      "max_workers": 10,
      "sell_multiplier": 0.60,
      "worker_roles": ["Sales Agent", "Mechanic", "Receptionist", "Finance Advisor", "Manager"],
      "worker_base_salary": 300,
      "upgrades": {
          "showroom_upgrade": {"name": "Premium Showroom", "emoji": "\u2728",             "cost": 60_000,  "income_bonus": 0.20, "req_level": 2},
          "luxury_models":    {"name": "Luxury Models",    "emoji": "\U0001f3ce\ufe0f",  "cost": 120_000, "income_bonus": 0.30, "req_level": 4},
          "financing_dept":   {"name": "Financing Dept",   "emoji": "\U0001f4b3",         "cost": 80_000,  "income_bonus": 0.20, "req_level": 3},
          "auction_house":    {"name": "Auction House",    "emoji": "\U0001f528",         "cost": 200_000, "income_bonus": 0.40, "req_level": 8},
      },
  },
  "factory": {
      "name": "Factory", "emoji": "\U0001f3ed",
      "description": "An industrial powerhouse producing goods at scale.",
      "base_cost": 250_000,
      "base_income_per_hour": 3_500,
      "base_maintenance_per_hour": 900,
      "max_workers": 20,
      "sell_multiplier": 0.60,
      "worker_roles": ["Operator", "Engineer", "Quality Control", "Foreman", "Manager"],
      "worker_base_salary": 350,
      "upgrades": {
          "automation":    {"name": "Automation Line", "emoji": "\U0001f916",     "cost": 100_000, "income_bonus": 0.25, "req_level": 2},
          "solar_panels":  {"name": "Solar Panels",    "emoji": "\u2600\ufe0f",  "cost": 80_000,  "income_bonus": 0.15, "req_level": 1},
          "r_and_d_lab":   {"name": "R&D Lab",         "emoji": "\U0001f52c",     "cost": 150_000, "income_bonus": 0.25, "req_level": 5},
          "global_export": {"name": "Global Export",   "emoji": "\U0001f30d",     "cost": 300_000, "income_bonus": 0.45, "req_level": 9},
      },
  },
  "arcade": {
      "name": "Arcade", "emoji": "\U0001f579\ufe0f",
      "description": "A retro-futuristic gaming paradise packed with tokens and fun.",
      "base_cost": 45_000,
      "base_income_per_hour": 700,
      "base_maintenance_per_hour": 130,
      "max_workers": 5,
      "sell_multiplier": 0.60,
      "worker_roles": ["Technician", "Cashier", "Security", "Manager"],
      "worker_base_salary": 145,
      "upgrades": {
          "vr_zone":          {"name": "VR Zone",          "emoji": "\U0001f97d", "cost": 30_000,  "income_bonus": 0.20, "req_level": 1},
          "tournament_stage": {"name": "Tournament Stage", "emoji": "\U0001f3c6", "cost": 45_000,  "income_bonus": 0.20, "req_level": 3},
          "prize_counter":    {"name": "Prize Counter",    "emoji": "\U0001f381", "cost": 25_000,  "income_bonus": 0.15, "req_level": 2},
          "esports_arena":    {"name": "eSports Arena",    "emoji": "\U0001f3ae", "cost": 120_000, "income_bonus": 0.35, "req_level": 7},
      },
  },
}


# ─────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────

def get_business(business_id: str) -> dict | None:
  return businesses_col.find_one({"_id": business_id})


def get_owner_businesses(owner_id: str) -> list[dict]:
  return list(businesses_col.find({"owner_id": owner_id}))


def get_xp_for_next_level(level: int) -> int:
  if level >= len(XP_PER_LEVEL):
      return 999_999_999
  return XP_PER_LEVEL[level]


# ─────────────────────────────────────────────────────────
# INCOME ENGINE
# ─────────────────────────────────────────────────────────

def compute_income(business: dict) -> dict:
  """
  Calculate pending income/expenses for a business WITHOUT writing to DB.
  Returns: hours_pending, gross_income, maintenance, worker_salaries, net, xp_earned
  """
  btype         = BUSINESS_TYPES[business["type"]]
  now           = time.time()
  last          = business.get("last_collected", now)
  elapsed_hours = min((now - last) / 3600.0, MAX_ACCUMULATION_HOURS)

  level    = business.get("level", 1)
  rep      = business.get("reputation", 50)
  upgrades = business.get("upgrades", [])
  workers  = business.get("workers", [])

  base    = btype["base_income_per_hour"] * elapsed_hours
  lv_mult = LEVEL_INCOME_MULT[min(level, len(LEVEL_INCOME_MULT) - 1)]

  # Upgrades stack additively
  upgrade_bonus = 1.0
  for upg_id in upgrades:
      upg = btype["upgrades"].get(upg_id)
      if upg:
          upgrade_bonus += upg["income_bonus"]

  # Each worker contributes 15% of their (efficiency - 1.0)
  worker_bonus = 1.0
  for w in workers:
      worker_bonus += (w.get("efficiency", 1.0) - 1.0) * 0.15

  rep_mult = reputation_multiplier(rep)
  gross    = int(base * lv_mult * upgrade_bonus * worker_bonus * rep_mult)

  maintenance     = int(btype["base_maintenance_per_hour"] * elapsed_hours)
  worker_salaries = int(sum(w.get("salary", 0) for w in workers) * elapsed_hours)
  net             = gross - maintenance - worker_salaries
  xp_earned       = max(1, int(elapsed_hours * level * 10))

  return {
      "hours_pending":   round(elapsed_hours, 2),
      "gross_income":    gross,
      "maintenance":     maintenance,
      "worker_salaries": worker_salaries,
      "net":             net,
      "xp_earned":       xp_earned,
  }


def collect_income(business_id: str) -> dict:
  """Collect pending income, apply XP/level-up, update reputation."""
  business = get_business(business_id)
  if not business:
      return {"error": "Business not found."}

  result = compute_income(business)
  now    = time.time()

  new_xp     = business.get("xp", 0) + result["xp_earned"]
  new_level  = business.get("level", 1)
  leveled_up = False

  while new_level < len(XP_PER_LEVEL) and new_xp >= XP_PER_LEVEL[new_level]:
      new_xp    -= XP_PER_LEVEL[new_level]
      new_level += 1
      leveled_up = True

  new_rep = min(100, business.get("reputation", 50) + 2)

  businesses_col.update_one(
      {"_id": business_id},
      {
          "$set": {
              "last_collected": now,
              "xp":             new_xp,
              "level":          new_level,
              "reputation":     new_rep,
          },
          "$inc": {
              "total_earned": max(0, result["net"]),
              "total_spent":  result["maintenance"] + result["worker_salaries"],
          },
      },
  )

  result["leveled_up"] = leveled_up
  result["new_level"]  = new_level
  result["new_rep"]    = new_rep
  return result


# ─────────────────────────────────────────────────────────
# BUSINESS OPERATIONS
# ─────────────────────────────────────────────────────────

def buy_business(owner_id: str, btype_key: str, name: str) -> dict:
  if btype_key not in BUSINESS_TYPES:
      return {"error": f"Unknown business type '{btype_key}'."}
  now         = time.time()
  short_id    = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
  business_id = f"{btype_key[:3].upper()}-{short_id}"
  doc = {
      "_id":            business_id,
      "owner_id":       owner_id,
      "type":           btype_key,
      "name":           name,
      "level":          1,
      "xp":             0,
      "reputation":     50,
      "workers":        [],
      "upgrades":       [],
      "last_collected": now,
      "founded_at":     now,
      "total_earned":   0,
      "total_spent":    0,
      "visits":         0,
  }
  businesses_col.insert_one(doc)
  return {"business_id": business_id, "doc": doc}


def apply_upgrade(business_id: str, upgrade_id: str) -> dict:
  business = get_business(business_id)
  if not business:
      return {"error": "Business not found."}
  btype   = BUSINESS_TYPES[business["type"]]
  upgrade = btype["upgrades"].get(upgrade_id)
  if not upgrade:
      return {"error": "Invalid upgrade ID."}
  if business.get("level", 1) < upgrade["req_level"]:
      return {"error": f'Requires Business Level {upgrade["req_level"]}.'}
  if upgrade_id in business.get("upgrades", []):
      return {"error": "Upgrade already purchased."}
  businesses_col.update_one({"_id": business_id}, {"$push": {"upgrades": upgrade_id}})
  return {"ok": True, "upgrade": upgrade}


def hire_worker(business_id: str) -> dict:
  business = get_business(business_id)
  if not business:
      return {"error": "Business not found."}
  btype   = BUSINESS_TYPES[business["type"]]
  workers = business.get("workers", [])
  if len(workers) >= btype["max_workers"]:
      return {"error": f'Max workers ({btype["max_workers"]}) already reached.'}

  name       = random.choice(WORKER_NAMES)
  role       = random.choice(btype["worker_roles"])
  base_sal   = btype["worker_base_salary"]
  salary     = int(base_sal * random.uniform(0.80, 1.20))
  efficiency = round(random.uniform(0.80, 1.30), 2)
  worker     = {
      "name":       name,
      "role":       role,
      "salary":     salary,
      "efficiency": efficiency,
      "level":      1,
      "xp":         0,
      "hired_at":   int(time.time()),
  }
  hire_cost = salary * 5
  businesses_col.update_one({"_id": business_id}, {"$push": {"workers": worker}})
  return {"ok": True, "worker": worker, "hire_cost": hire_cost}


def fire_worker(business_id: str, worker_index: int) -> dict:
  business = get_business(business_id)
  if not business:
      return {"error": "Business not found."}
  workers = business.get("workers", [])
  if worker_index < 0 or worker_index >= len(workers):
      return {"error": "Invalid worker index."}
  fired = workers[worker_index]
  workers.pop(worker_index)
  businesses_col.update_one({"_id": business_id}, {"$set": {"workers": workers}})
  return {"ok": True, "fired": fired}


def sell_business(business_id: str) -> dict:
  business = get_business(business_id)
  if not business:
      return {"error": "Business not found."}
  btype          = BUSINESS_TYPES[business["type"]]
  upgrades_owned = business.get("upgrades", [])
  upgrade_value  = sum(btype["upgrades"][u]["cost"] for u in upgrades_owned if u in btype["upgrades"])
  level          = business.get("level", 1)
  sell_price     = int(
      (btype["base_cost"] + upgrade_value)
      * btype["sell_multiplier"]
      * (1 + (level - 1) * 0.05)
  )
  businesses_col.delete_one({"_id": business_id})
  return {"ok": True, "sell_price": sell_price, "name": business["name"]}


def rename_business(business_id: str, new_name: str) -> dict:
  if not get_business(business_id):
      return {"error": "Business not found."}
  businesses_col.update_one({"_id": business_id}, {"$set": {"name": new_name}})
  return {"ok": True}


def increment_visits(business_id: str) -> None:
  businesses_col.update_one({"_id": business_id}, {"$inc": {"visits": 1}})


def get_leaderboard(limit: int = 10) -> list[dict]:
  return list(businesses_col.find({}, sort=[("total_earned", -1)]).limit(limit))
