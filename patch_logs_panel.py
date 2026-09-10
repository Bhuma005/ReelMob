with open('frontend-react/src/App.jsx', 'r', encoding='utf-8') as f:
    jsx = f.read()

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

anchor = "              {previewVideo && ("
if 'Full Activity History' not in jsx:
    jsx = jsx.replace(anchor, logs_panel_html + "\n\n              " + anchor, 1)
    with open('frontend-react/src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(jsx)
    print("Injected logs table panel")
else:
    print("Already injected")
