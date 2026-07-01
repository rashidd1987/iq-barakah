#!/bin/bash
cd /app/ACTIVE/pwa_api
exec python -m uvicorn main:app --host 0.0.0.0 --port 80
