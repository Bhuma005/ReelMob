import json
import subprocess
import os
import glob

def get_real_dimensions(file_path):
    ffprobe_path = os.path.join("backend", "ffprobe.exe")
    if not os.path.exists(ffprobe_path):
        ffprobe_path = "ffprobe"
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:stream_tags=rotate",
        "-of", "json",
        file_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        info = json.loads(result.stdout)
        stream = info.get("streams", [{}])[0]
        w = stream.get("width")
        h = stream.get("height")
        tags = stream.get("tags", {})
        rotate = tags.get("rotate", "0")
        if str(rotate) in ["90", "-90", "270", "-270", "90.0", "-90.0", "270.0", "-270.0"]:
            w, h = h, w
            
        # For newer ffmpeg versions, rotation might be in side_data_list
        if not rotate or str(rotate) == "0":
            # Let's try side data
            cmd_side = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream_side_data=rotation",
                "-of", "json",
                file_path
            ]
            res_side = subprocess.run(cmd_side, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            info_side = json.loads(res_side.stdout)
            side_data_list = info_side.get("streams", [{}])[0].get("side_data_list", [])
            for sd in side_data_list:
                if "rotation" in sd:
                    rot = sd["rotation"]
                    if abs(int(rot)) == 90 or abs(int(rot)) == 270:
                        w, h = h, w
        return w, h
    except Exception as e:
        print("error", e)
        return None, None

files = glob.glob("downloads/*.mp4")
for f in files[:5]:
    print(f, get_real_dimensions(f))
