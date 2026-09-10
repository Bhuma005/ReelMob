import re

# 1. Update backend/main.py to guarantee replace
with open('backend/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

anchor = '''        # 3. Upload overwritten video back to Supabase
        with open(temp_out, "rb") as f:
            sb.storage.from_("reelgrab-videos").update(storage_path, f, file_options={"content-type": "video/mp4", "upsert": "true"})'''

replacement = '''        # 3. Upload overwritten video back to Supabase
        sb.storage.from_("reelgrab-videos").remove([storage_path])
        with open(temp_out, "rb") as f:
            sb.storage.from_("reelgrab-videos").upload(storage_path, f, file_options={"content-type": "video/mp4"})'''

if anchor in c:
    c = c.replace(anchor, replacement)
    with open('backend/main.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Backend update logic fixed")
else:
    print("Backend anchor not found!")


# 2. Update React to force video reload
with open('frontend-react/src/App.jsx', 'r', encoding='utf-8') as f:
    c = f.read()

react_anchor = '''                        <video 
                            controls 
                            preload="metadata"
                            autoPlay 
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                            src={previewVideo.public_url} 
                        />'''

react_replacement = '''                        <video 
                            key={previewVideo.public_url}
                            controls 
                            preload="metadata"
                            autoPlay 
                            style={{ width: '100%', height: '100%', objectFit: 'contain' }} 
                            src={previewVideo.public_url} 
                        />'''

if react_anchor in c:
    c = c.replace(react_anchor, react_replacement)
    with open('frontend-react/src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(c)
    print("React video key fixed")
else:
    print("React anchor not found")
