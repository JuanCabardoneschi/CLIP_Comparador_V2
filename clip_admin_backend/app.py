"""
Compatibility wrapper - imports from wsgi.py
This file exists for Railway compatibility
"""
from wsgi import app, create_app

if __name__ == "__main__":
    app.run()
