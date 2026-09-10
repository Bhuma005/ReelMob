import re

with open('frontend-react/src/App.jsx', 'r', encoding='utf-8') as f:
    c = f.read()

anchor = '''      .then(data => {
        setAutomationResult(data.automation_details);
        setAutoStatusText('✅ Scheduled Successfully');
        showToast("Post scheduled securely!");
        setIsLoading(false);
      })
      .catch(e => {
        setAutoStatusText('❌ Error: ' + e);
        setIsLoading(false);
      });'''

replacement = '''      .then(data => {
        if (data.status === 'error') {
            setAutoStatusText('❌ Error: ' + data.message);
            showToast("Failed: " + data.message);
        } else {
            setAutomationResult(data.automation_details);
            setAutoStatusText('✅ Scheduled Successfully');
            showToast("Post scheduled securely!");
        }
        setIsLoading(false);
      })
      .catch(e => {
        setAutoStatusText('❌ Error: ' + e);
        setIsLoading(false);
      });'''

if anchor in c:
    c = c.replace(anchor, replacement)
    with open('frontend-react/src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(c)
    print("Fixed React UI bug to show errors")
else:
    print("Anchor not found in App.jsx")
