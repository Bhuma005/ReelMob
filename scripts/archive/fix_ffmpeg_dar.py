import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

anchor = '''        # 2. Run FFmpeg (blur background padding technique)
        filter_complex = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,boxblur=20:20,crop={W}:{H}[bg];[bg][fg]overlay=(W-w)/2:(H-h)/2"'''

replacement = '''        # 2. Run FFmpeg (blur background padding technique)
        filter_complex = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,boxblur=20:20,crop={W}:{H}[bg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,setdar={W}/{H}"'''

if anchor in c:
    c = c.replace(anchor, replacement)
    with open('backend/main.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Injected FFmpeg SAR/DAR fix")
else:
    print("Anchor not found!")
