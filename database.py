import os
import ssl
import certifi
import pymongo

# Python 3.14 changed TLS defaults; build an explicit context to stay
# compatible with MongoDB Atlas on any Python version.
_ssl_ctx = ssl.create_default_context(cafile=certifi.where())
_ssl_ctx.check_hostname = True
_ssl_ctx.verify_mode = ssl.CERT_REQUIRED

client = pymongo.MongoClient(
    os.getenv("MONGO_URI"),
    tls=True,
    tlsCAFile=certifi.where(),
)
db = client["protox_bot"]

pets_col = db["pets"]
warns_col = db["warns"]
eco_col = db["economy"]
memory_col = db["memory"]
starboard_col = db["starboard_config"]
starboard_messages_col = db["starboard_messages"]
tutorial_col = db["tutorials"]
