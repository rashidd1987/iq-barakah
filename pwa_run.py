import subprocess, sys, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ACTIVE', 'pwa_api'))
sys.exit(subprocess.call([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '80']))
