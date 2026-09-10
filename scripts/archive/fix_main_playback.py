import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

anchor = '''            "-lavfi", filter_complex,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            temp_out'''

replacement = '''            "-lavfi", filter_complex,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "copy",
            temp_out'''

if anchor in c:
    c = c.replace(anchor, replacement)
    with open('backend/main.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Injected main.py faststart")
else:
    print("Anchor not found in main.py")
