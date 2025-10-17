"""
Simple test script to verify the OME blueprint works correctly
"""

from flask import Flask
from ome_blueprint import ome_blueprint

def test_blueprint_registration():
    """Test that the blueprint registers correctly"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Register the blueprint
    app.register_blueprint(ome_blueprint, url_prefix='/OME')
    
    # Test with app context
    with app.app_context():
        # Check that routes are registered
        rules = [str(rule) for rule in app.url_map.iter_rules()]
        
        print("Registered routes:")
        for rule in sorted(rules):
            if '/OME' in rule:
                print(f"  [OK] {rule}")
        
        # Verify key routes exist
        expected_routes = [
            '/OME/',
            '/OME/search',
            '/OME/health',
            '/OME/upload_csv',
            '/OME/download/<session_id>'
        ]
        
        all_present = True
        for route in expected_routes:
            if route not in rules:
                print(f"  [FAIL] Missing route: {route}")
                all_present = False
        
        if all_present:
            print("\n[SUCCESS] All expected routes are registered!")
            print("[SUCCESS] Blueprint integration successful!")
            return True
        else:
            print("\n[FAIL] Some routes are missing!")
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("Testing OME Blueprint")
    print("=" * 60)
    
    success = test_blueprint_registration()
    
    if success:
        print("\n" + "=" * 60)
        print("Ready to integrate into your Flask app!")
        print("=" * 60)
        print("\nQuick integration:")
        print("  from ome_blueprint import ome_blueprint")
        print("  app.register_blueprint(ome_blueprint, url_prefix='/OME')")
        print("\nThen access at: http://your-app/OME/")
        print("=" * 60)

