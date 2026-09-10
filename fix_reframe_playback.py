import re

with open('smart_reframe.py', 'r', encoding='utf-8') as f:
    c = f.read()

anchor = '''        "-c:a", "aac",
        # Fix missing DAR via lavfi is not needed on copy, but let's set metadata explicitly
        "-aspect", f"{target_w}:{target_h}",
        output_path'''

replacement = '''        "-c:a", "aac",
        "-movflags", "+faststart",
        # Fix missing DAR via lavfi is not needed on copy, but let's set metadata explicitly
        "-aspect", f"{target_w}:{target_h}",
        output_path'''

if anchor in c:
    c = c.replace(anchor, replacement)
    with open('smart_reframe.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Injected smart_reframe.py faststart")
else:
    print("Anchor not found in smart_reframe")
