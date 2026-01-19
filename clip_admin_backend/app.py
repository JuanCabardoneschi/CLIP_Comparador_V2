"""
Compatibility wrapper - imports from wsgi.py
This file exists for Railway compatibility
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run directly from wsgi
if __name__ == "__main__":
    from wsgi import app
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
