import json
import urllib.request
import re
from backend.ai_pipeline import generate_shorts_content

def test():
    try:
        res = generate_shorts_content(
            video_title="TEST TITLE",
            video_description="TEST DESC",
            duration_seconds=10,
            target_region="India",
            temperature=0.8
        )
        print("Success!")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print("Fail!", e)

if __name__ == "__main__":
    test()
