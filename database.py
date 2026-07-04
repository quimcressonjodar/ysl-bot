import os
import certifi
import pymongo

# Python 3.14 + OpenSSL 3.x breaks TLS handshake with MongoDB Atlas.
# tlsAllowInvalidCertificates bypasses the broken handshake while keeping
# traffic encrypted. Remove once Render is pinned to Python 3.11.
client = pymongo.MongoClient(
    os.getenv("MONGO_URI"),
    tls=True,
    tlsAllowInvalidCertificates=True,
)
db = client["protox_bot"]

pets_col = db["pets"]
warns_col = db["warns"]
eco_col = db["economy"]
memory_col = db["memory"]
starboard_col = db["starboard_config"]
starboard_messages_col = db["starboard_messages"]
tutorial_col = db["tutorials"]
