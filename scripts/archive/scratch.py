import json
import subprocess
import cv2
import glob

def get_ffprobe_dims(file_path):
    cmd = [
        "backend/ffprobe.exe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:stream_tags=rotate",
        "-of", "json",
        file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout

files = glob.glob("downloads/*.mp4")
if files:
    print(files[0])
    print(get_ffprobe_dims(files[0]))
