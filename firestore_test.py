import os
import json
from google.cloud import firestore
from google.oauth2 import service_account

def check_firestore():
    creds_value = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print("Using credentials from env (first 60 chars):", (creds_value[:60] + '...') if creds_value else None)

    try:
        if not creds_value:
            raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS env var not set")

        # If the env var starts with '{', assume it's JSON directly in .env
        if creds_value.strip().startswith("{"):
            info = json.loads(creds_value)
            creds = service_account.Credentials.from_service_account_info(info)
            project_id = info.get("project_id")
            db = firestore.Client(credentials=creds, project=project_id)
        else:
            # Otherwise treat it as a path to a JSON file
            if not os.path.exists(creds_value):
                raise FileNotFoundError(f"File {creds_value} was not found.")
            db = firestore.Client()

        # Try a test write/read
        doc_ref = db.collection("health_check").document("ping_from_vs_code")
        doc_ref.set({"status": "ok", "source": "COM-AI v3", "env_type": "test"})
        doc = doc_ref.get()
        print("✅ Firestore connected! Document content:", doc.to_dict())

    except Exception as e:
        print("❌ Firestore failed:", e)

if __name__ == "__main__":
    check_firestore()
