import sys
sys.path.insert(0, r'C:\Personal\CLIP_Comparador_V2\clip_admin_backend')

try:
    from app.blueprints.api import bp
    print("Import OK")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
