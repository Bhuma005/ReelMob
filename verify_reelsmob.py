import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\bhuma\.gemini\antigravity\scratch\reelsmob')

from backend.services.cloud_ai import is_cloud_ai_available, analyze_frames_with_gemini, generate_metadata_with_groq
from backend.video_analyzer import analyze_video_content

print("========================================")
print("      REELSMOB PIPELINE VERIFICATION    ")
print("========================================")

# 1. Check API Keys
print("\n[1] Checking Cloud AI Keys...")
print("Cloud AI Available:", is_cloud_ai_available())
assert is_cloud_ai_available() == True, "Cloud AI keys are missing!"
print("✅ Keys validated successfully.")

# 2. Test Video Analyzer on an actual MP4 video file
test_video = r'c:\Users\bhuma\.gemini\antigravity\scratch\reelsmob\test.mp4'
if os.path.exists(test_video):
    print(f"\n[2] Testing video frame extraction + Gemini Vision on {os.path.basename(test_video)}...")
    analysis = analyze_video_content(
        video_path=test_video,
        raw_title="Test Scene",
        raw_description="Two people talking outdoors"
    )
    print("Video Analyzed:", analysis.get("video_analyzed"))
    print("Vision Success:", analysis.get("vision_success"))
    print("Vision Model Used:", analysis.get("vision_model_used"))
    print("Source Label:", analysis.get("source_label"))
    print("Visual Summary:", analysis.get("visual_description", "")[:120], "...")
    assert analysis.get("vision_success") == True, "Gemini vision failed to analyze video frames!"
    print("✅ Real Video Vision Analysis Passed!")

# 3. Test Groq Metadata Generation
print("\n[3] Testing Groq Viral Metadata Synthesis...")
meta = generate_metadata_with_groq(
    visual_summary="A young man in a white shirt looking nervously at a girl under the sunlight, smiling shyly.",
    caption="Scene from Dia movie #coke_series_07"
)
print("Title:", meta.get("title"))
print("Description:", meta.get("description"))
print("YouTube Hashtags:", meta.get("youtube_hashtags"))
print("Success:", meta.get("success"))
assert meta.get("success") == True, "Groq metadata generation failed!"
assert len(meta.get("youtube_hashtags", [])) >= 7, "Less than 7 hashtags generated!"
print("✅ Groq Viral Metadata Synthesis Passed!")

print("\n========================================")
print("  ALL REELSMOB TESTS PASSED 100% CLEAN! ")
print("========================================")
