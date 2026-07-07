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
