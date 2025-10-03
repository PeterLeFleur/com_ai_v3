"""
Firebase/Firestore client initialization using Google Application Credentials
"""

import os
import logging
from google.cloud import firestore
from google.oauth2 import service_account

logger = logging.getLogger(__name__)
_firebase_client = None


def init_firebase():
    """
    Initialize async Firestore client using GOOGLE_APPLICATION_CREDENTIALS.
    This is the standard Google Cloud SDK environment variable.
    Returns cached client on subsequent calls.
    """
    global _firebase_client
    
    if _firebase_client is None:
        # Use standard Google Cloud env var
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase-credentials.json")
        
        logger.info(f"Initializing Firebase Admin SDK with credentials: {creds_path}")
        
        if not os.path.exists(creds_path):
            raise FileNotFoundError(
                f"Firebase Admin SDK credentials not found at {creds_path}. "
                "Set GOOGLE_APPLICATION_CREDENTIALS in .env or place firebase-credentials.json in project root."
            )
        
        try:
            credentials = service_account.Credentials.from_service_account_file(creds_path)
            _firebase_client = firestore.AsyncClient(credentials=credentials)
            logger.info(f"Firebase Admin SDK initialized successfully (project: {credentials.project_id})")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {e}", exc_info=True)
            raise
    
    return _firebase_client