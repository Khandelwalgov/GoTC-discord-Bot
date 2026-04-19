import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Initialize only if not already initialized
if not firebase_admin._apps:
    # Check if we are using the JSON string (Cloud/Render) 
    # or a local file (Local Dev)
    firebase_json = os.getenv("FIREBASE_CONFIG")
    
    if firebase_json:
        # Load credentials from the environment variable string
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback for local development
        cred = credentials.Certificate("serviceAccount.json")
        
    firebase_admin.initialize_app(cred)

db = firestore.client()