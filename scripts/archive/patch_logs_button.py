with open('frontend-react/src/App.jsx', 'r', encoding='utf-8') as f:
    jsx = f.read()

anchor = ">Saved Videos Dashboard</div>"
replacement = """>Saved Videos Dashboard</div>
              <button onClick={() => { setShowLogsPanel(!showLogsPanel); if(!showLogsPanel) loadAuditLogs(); }} style={{ background: showLogsPanel ? 'var(--accent)' : 'rgba(255,255,255,0.08)', border: '1px solid var(--border)', color: showLogsPanel ? '#000' : 'var(--text-primary)', padding: '6px 16px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '10px' }}>📋 {showLogsPanel ? 'Hide' : 'Show'} Activity Logs</button>"""

if 'Activity Logs' not in jsx:
    jsx = jsx.replace(anchor, replacement, 1)
    with open('frontend-react/src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(jsx)
    print("Added logs toggle button")
else:
    print("Already exists")
