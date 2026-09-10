import re

with open('fit_to_canvas.py', 'r', encoding='utf-8') as f:
    c = f.read()

anchor1 = '''            "-i", input_path,
            "-vf", f"scale={canvas_w}:{canvas_h}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            output_path'''

replacement1 = '''            "-i", input_path,
            "-vf", f"scale={canvas_w}:{canvas_h}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "copy",
            output_path'''

anchor2 = '''            "-i", input_path,
            "-lavfi", filter_complex,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy", 
            output_path'''

replacement2 = '''            "-i", input_path,
            "-lavfi", filter_complex,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "copy", 
            output_path'''

if anchor1 in c and anchor2 in c:
    c = c.replace(anchor1, replacement1).replace(anchor2, replacement2)
    with open('fit_to_canvas.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Injected faststart and pix_fmt")
else:
    print("Anchors not found")
