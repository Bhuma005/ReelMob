import re

with open('frontend-react/src/App.jsx', 'r', encoding='utf-8') as f:
    c = f.read()

anchor = '''                        {/* Video Player Side */}
                        <div style={{ flex: '1 1 300px', maxWidth: '350px' }}>
                            <div style={{ background: '#000', borderRadius: '8px', overflow: 'hidden', border: '1px solid #3f3f46', aspectRatio: '9/16', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                {previewVideo.public_url ? (
                                    <video controls preload="metadata" autoPlay style={{ width: '100%', height: '100%', objectFit: 'cover' }} src={previewVideo.public_url} />
                                ) : (
                                    <span style={{ color: '#555' }}>Video missing</span>
                                )}
                            </div>'''

replacement = '''                        {/* Video Player Side */}
                        <div style={{ flex: '1 1 300px', maxWidth: '350px' }}>
                            <div style={{ background: '#000', borderRadius: '8px', overflow: 'hidden', border: '1px solid #3f3f46', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                {previewVideo.public_url ? (
                                    <video key={previewVideo.public_url} controls preload="metadata" autoPlay style={{ width: '100%', maxHeight: '600px', objectFit: 'contain' }} src={previewVideo.public_url} />
                                ) : (
                                    <span style={{ color: '#555' }}>Video missing</span>
                                )}
                            </div>'''

if anchor in c:
    c = c.replace(anchor, replacement)
    with open('frontend-react/src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(c)
    print("React CSS fixed")
else:
    print("React anchor not found")
