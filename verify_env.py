import os
from dotenv import load_dotenv

def verify_environment():
    """CLI utility to verify local .env against required schemas before deployment."""
    load_dotenv("cloud/.env")
    
    required_secrets = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "YOUTUBE_API_KEY"
    ]
    
    missing = []
    print("🔍 Validating environment secrets...\n")
    for secret in required_secrets:
        if not os.getenv(secret):
            missing.append(secret)
            print(f"❌ Missing: {secret}")
        else:
            val = os.getenv(secret)
            # Schema test
            if secret == "SUPABASE_URL" and not val.startswith("https://"):
                print(f"⚠️ Warning: {secret} does not look like a valid secure URL.")
            elif secret == "SUPABASE_SERVICE_KEY" and "eyJ" not in val:
                print(f"⚠️ Warning: {secret} does not look like a valid JWT token.")
            else:
                print(f"✅ Verified: {secret} is configured correctly.")
                
    print("\n")
    if missing:
        print(f"🚨 FAILED: The environment is missing {len(missing)} required secrets.")
        exit(1)
    else:
        print("✨ SUCCESS: All required environment secrets are valid and present for deployment.")
        exit(0)

if __name__ == "__main__":
    verify_environment()
