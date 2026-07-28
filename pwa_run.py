import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ACTIVE', 'pwa_api'))
import uvicorn
from main import app
uvicorn.run(app, host='0.0.0.0', port=80)
