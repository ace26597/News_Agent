#!/usr/bin/env python3
"""
Simple runner script for the Pharma News Research Agent
This script ensures the application runs with basic global Python
"""

import sys
import subprocess
import os

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        import flask
        import requests
        print("✅ All dependencies are available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Installing missing dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "requests"])
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            return False

def main():
    """Main function to run the pharma search application"""
    print("=" * 60)
    print("🔬 Pharma News Research Agent")
    print("=" * 60)
    print("Starting application...")
    
    # Check dependencies
    if not check_dependencies():
        print("Please install Flask and requests manually:")
        print("pip install flask requests")
        return
    
    # Import and run the application
    try:
        from medical_search_simple import app
        print("✅ Application loaded successfully")
        print("🌐 Opening browser to: http://127.0.0.1:5000")
        print("📅 Default search range: Last 7 days")
        print("🔬 Focus: Pharmaceutical news and clinical research")
        print("=" * 60)
        print("Press Ctrl+C to stop the server")
        print("=" * 60)
        
        app.run(host='127.0.0.1', port=5000, debug=False)
        
    except Exception as e:
        print(f"❌ Error starting application: {str(e)}")
        print("Please check your Python installation and try again")

if __name__ == "__main__":
    main()
