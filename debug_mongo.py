import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
print(f"Testing connection to: {MONGO_URI.split('@')[-1] if '@' in MONGO_URI else 'localhost/default'}") 
# Hiding password in print for security

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    db = client["financas_bot"]
    # Trigger a connection
    client.admin.command('ping')
    print("Connection successful!")
    
    # Try to access the specific database
    print(f"Collections: {db.list_collection_names()}")
    
except OperationFailure as e:
    print(f"Authentication/Authorization Error: {e}")
except ServerSelectionTimeoutError as e:
    print(f"Connection Timeout: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
