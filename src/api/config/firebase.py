# api/config/firebase.py
"""
Firebase initialization for COM-AI v3
Provides Firestore client for live UI mirror (PostgreSQL is authoritative)
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path

def init_firebase():
    """
    Initialize Firebase Admin SDK
    Returns Firestore client or None if credentials missing
    """
    try:
        # Path to service account key
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'firebase-credentials.json')
        
        if not os.path.exists(cred_path):
            print(f"⚠️ Firebase credentials not found at {cred_path}")
            return None
        
        # Initialize Firebase Admin (if not already initialized)
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'projectId': os.getenv('FIREBASE_PROJECT_ID', 'cerebrum-cadre')
            })
        
        # Return Firestore client
        db = firestore.client()
        print("✅ Firebase/Firestore initialized successfully")
        return db
        
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        return None

# Initialize on module import
firestore_db = init_firebase()