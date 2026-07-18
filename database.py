import os
import pymongo

client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client["protox_bot"]

pets_col = db["pets"]
warns_col = db["warns"]
eco_col = db["economy"]
memory_col = db["memory"]
starboard_col = db["starboard_config"]
starboard_messages_col = db["starboard_messages"]
tutorial_col = db["tutorials"]
bot_state_col = db["bot_state"]
businesses_col = db["businesses"]
modmail_col = db["modmail"]

# Dashboard collections
bot_guilds_col = db["bot_guilds"]
dashboard_modules_col = db["dashboard_modules"]
bot_logs_col = db["bot_logs"]

# Index for efficient log queries (newest first per guild)
try:
    bot_logs_col.create_index([("guild_id", 1), ("timestamp", -1)])
    bot_logs_col.create_index([("guild_id", 1), ("type", 1), ("timestamp", -1)])
except Exception:
    pass
