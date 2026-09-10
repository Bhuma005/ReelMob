import sys, os, urllib.error
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\bhuma\.gemini\antigravity\scratch\reelsmob')
from backend.services.cloud_ai import is_cloud_ai_available, generate_metadata_with_groq

print("Testing ReelsMob Cloud AI...")
print("Cloud AI available:", is_cloud_ai_available())

try:
    res = generate_metadata_with_groq(
        "A nervous college boy carrying books walks across campus, sees a pretty senior girl smiling at him, drops all his papers in shock, everyone laughs.",
        caption="College love scene from the movie Dia #coke_series_07"
    )
    print("RES:", res)
except Exception as e:
    print("Exception:", e)

