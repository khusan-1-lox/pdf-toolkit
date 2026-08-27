import subprocess, time, sys, os, requests

frontend_dir = r'C:\pdf-toolkit\frontend'

# Start frontend dev server in background
proc = subprocess.Popen([
    sys.executable, '-m', 'next', 'dev', '--hostname', '127.0.0.1'
], cwd=frontend_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Wait for it to start
time.sleep(10)

# Test the dashboard
try:
    r = requests.get('http://127.0.0.1:3000', timeout=10)
    print('Frontend status:', r.status_code)
    print('PDF Toolkit in title:', 'PDF Toolkit' in r.text)
    print('Length:', len(r.text))
    print('Tools count (href /tools/):', r.text.count('/tools/'))
    
    # Check a few tool pages
    for slug in ['merge', 'split', 'organize-pdf']:
        r2 = requests.get(f'http://127.0.0.1:3000/tools/{slug}', timeout=10)
        has_unknown = 'Unknown tool' in r2.text
        print(f'{slug}: unknown={has_unknown}')
except Exception as e:
    print('Error:', e)

print('\\n--- Test complete ---')
# Don't terminate the proc - it keeps the dev server running