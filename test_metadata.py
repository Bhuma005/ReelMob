import yt_dlp

try:
    with yt_dlp.YoutubeDL({'quiet':True, 'extract_flat':False}) as ydl:
        info = ydl.extract_info("https://www.instagram.com/reel/Da-m6P6zbXD", download=False)
        print("TITLE:", info.get('title'))
        print("DESC:", repr(info.get('description')))
        print("FORMATS:", len(info.get('formats', [])))
except Exception as e:
    print("FAILED", e)
