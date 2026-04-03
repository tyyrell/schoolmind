"""Quick start script for local development."""
import os, subprocess, sys
os.environ.setdefault("SECRET_KEY", "dev-secret-key-change-in-prod")
os.environ.setdefault("FLASK_DEBUG", "1")
subprocess.run([sys.executable, "app.py"])
