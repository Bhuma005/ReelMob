import os

# 1. Add audit logs API endpoint to backend
with open('backend/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

if '/api/dashboard/logs' not in c:
    new_route = """

@app.get("/api/dashboard/logs", summary="Get audit logs", description="Returns the audit log history.")
async def get_dashboard_logs():
    import os
    logs = []
    log_path = "reelgrab_audit.log"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                logs.append(line)
    logs.reverse()
    return {"logs": logs}
"""
    c = c + new_route
    with open('backend/main.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Injected logs endpoint")
else:
    print("Already exists")

# 2. Patch the frontend: add Logs tab + auto-refresh after schedule
with open('frontend-react/src/App.jsx', 'r', encoding='utf-8') as f:
    jsx = f.read()

# 2a. Add state for logs
state_anchor = "const [dashboardVideos, setDashboardVideos] = useState([]);"
state_replacement = """const [dashboardVideos, setDashboardVideos] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [showLogsPanel, setShowLogsPanel] = useState(false);"""

if 'auditLogs' not in jsx:
    jsx = jsx.replace(state_anchor, state_replacement)
    print("Added audit log state")

# 2b. After "Scheduled Successfully", auto-refresh dashboard
sched_anchor = "setAutoStatusText('✅ Scheduled Successfully');\n        showToast(\"Post scheduled securely!\");"
sched_replacement = """setAutoStatusText('✅ Scheduled Successfully');
        showToast("Post scheduled securely!");
        loadDashboardData();"""

if 'loadDashboardData();' not in jsx[jsx.find("Scheduled Successfully"):jsx.find("Scheduled Successfully")+200]:
    jsx = jsx.replace(sched_anchor, sched_replacement)
    print("Added auto-refresh after schedule")

# 2c. Add the Logs table UI and fetch function
# Find the closing of the dashboard sidebar section to inject our logs panel
logs_fetch = """
  const loadAuditLogs = () => {
    fetch(`${API_BASE}/api/dashboard/logs`).then(r => r.json()).then(data => {
      setAuditLogs(data.logs || []);
    }).catch(() => {});
  };
"""

if 'loadAuditLogs' not in jsx:
    # Inject after loadDashboardData definition
    load_anchor = "// Rendering Helpers"
    jsx = jsx.replace(load_anchor, logs_fetch + "\n  " + load_anchor)
    print("Added loadAuditLogs function")

# 2d. Add Logs button in the dashboard header area + logs table panel
logs_button = """<button onClick={() => { setShowLogsPanel(!showLogsPanel); if(!showLogsPanel) loadAuditLogs(); }} style={{ background: showLogsPanel ? 'var(--accent)' : 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', color: showLogsPanel ? '#000' : 'var(--text-primary)', padding: '6px 14px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}>📋 Activity Logs</button>"""

if 'Activity Logs' not in jsx:
    # Find the dashboard header with PENDING badge
    pending_anchor = """<span style={{ background: '#F59E0B', color: '#000', padding: '2px 10px', borderRadius: '10px', fontWeight: 'bold', fontSize: '0.7rem' }}>PENDING</span>"""
    if pending_anchor in jsx:
        jsx = jsx.replace(pending_anchor, pending_anchor + "\n              " + logs_button)
        print("Added logs button")

# 2e. Add the actual logs table panel right after the dashboard video list
logs_panel_html = """{showLogsPanel && (
              <div style={{ marginTop: '16px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', border: '1px solid var(--border)', overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>📋 Full Activity History</span>
                  <button onClick={loadAuditLogs} style={{ background: 'var(--accent)', border: 'none', color: '#000', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 'bold' }}>🔄 Refresh</button>
                </div>
                <div style={{ overflowX: 'auto', maxHeight: '300px', overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                    <thead>
                      <tr style={{ background: 'rgba(255,255,255,0.05)', position: 'sticky', top: 0 }}>
                        <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>Timestamp</th>
                        <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>Action</th>
                        <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLogs.length === 0 ? (
                        <tr><td colSpan={3} style={{ padding: '16px', textAlign: 'center', color: 'var(--text-muted)' }}>No logs yet</td></tr>
                      ) : auditLogs.map((log, idx) => {
                        const tsMatch = log.match(/\\[([^\\]]+)\\]/);
                        const ts = tsMatch ? tsMatch[1] : '';
                        const rest = log.replace(/\\[[^\\]]+\\]\\s*/, '');
                        const parts = rest.split(' | ');
                        const action = parts[0] || '';
                        const details = parts.slice(1).join(' | ');
                        const actionColor = action.includes('DELETED') ? '#FF4444' : action.includes('UPLOAD') ? '#00CC88' : 'var(--accent)';
                        return (
                          <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                            <td style={{ padding: '6px 12px', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: '0.72rem' }}>{ts ? new Date(ts).toLocaleString() : ''}</td>
                            <td style={{ padding: '6px 12px', whiteSpace: 'nowrap', color: actionColor, fontWeight: 'bold' }}>{action}</td>
                            <td style={{ padding: '6px 12px', color: 'var(--text-secondary)', maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{details}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}"""

if 'Full Activity History' not in jsx:
    # Find the closing of the dashboardVideos map
    videos_end = jsx.find("</div>", jsx.rfind("previewVideo &&"))
    # Better: find the section just before the preview modal
    close_anchor = "{/* ─── YouTube Shorts Studio Preview Modal ───"
    if close_anchor in jsx:
        jsx = jsx.replace(close_anchor, logs_panel_html + "\n\n            " + close_anchor)
        print("Added logs table panel")
    else:
        print("Could not find modal anchor for logs panel")

with open('frontend-react/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(jsx)

print("\nAll patches applied!")
