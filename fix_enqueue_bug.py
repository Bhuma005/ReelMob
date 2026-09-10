import re

with open('cloud/enqueue.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('        from datetime import datetime\n', '')

with open('cloud/enqueue.py', 'w', encoding='utf-8') as f:
    f.write(c)
print("Fixed UnboundLocalError bug inside enqueue_video!")
