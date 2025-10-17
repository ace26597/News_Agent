"""
Example Integration: How to use the OME Blueprint in your Flask app

This shows how to integrate the Pharma News Research Agent blueprint
into your existing Flask application at the /OME/ endpoint.
"""

from flask import Flask
from ome_blueprint import ome_blueprint

# Create your Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Register the OME blueprint at /OME/ prefix
# All routes from the blueprint will be accessible at /OME/*
app.register_blueprint(ome_blueprint, url_prefix='/OME')

# Example: Your existing routes
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Flask App with OME Blueprint</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 60px 40px;
                max-width: 700px;
                width: 100%;
                text-align: center;
            }
            
            h1 {
                color: #2c3e50;
                font-size: 2.5em;
                margin-bottom: 10px;
                font-weight: 700;
            }
            
            .subtitle {
                color: #7f8c8d;
                font-size: 1.1em;
                margin-bottom: 40px;
            }
            
            .feature-box {
                background: #f8f9fa;
                border-radius: 12px;
                padding: 30px;
                margin: 30px 0;
                border-left: 5px solid #667eea;
            }
            
            .feature-box h2 {
                color: #2c3e50;
                font-size: 1.8em;
                margin-bottom: 15px;
            }
            
            .feature-box p {
                color: #555;
                line-height: 1.8;
                margin-bottom: 20px;
            }
            
            .btn {
                display: inline-block;
                padding: 15px 40px;
                margin: 10px;
                border-radius: 50px;
                text-decoration: none;
                font-weight: 600;
                font-size: 1.1em;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
            
            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            
            .btn-primary:hover {
                transform: translateY(-3px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }
            
            .btn-secondary {
                background: #34495e;
                color: white;
            }
            
            .btn-secondary:hover {
                transform: translateY(-3px);
                box-shadow: 0 6px 20px rgba(52, 73, 94, 0.4);
            }
            
            .status {
                display: inline-block;
                padding: 8px 20px;
                background: #27ae60;
                color: white;
                border-radius: 20px;
                font-size: 0.9em;
                margin-top: 20px;
            }
            
            .features-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin: 30px 0;
            }
            
            .feature-item {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                text-align: left;
            }
            
            .feature-item h3 {
                color: #667eea;
                font-size: 1.2em;
                margin-bottom: 10px;
            }
            
            .feature-item p {
                color: #666;
                font-size: 0.95em;
                line-height: 1.6;
            }
            
            .emoji {
                font-size: 3em;
                margin-bottom: 20px;
            }
            
            @media (max-width: 768px) {
                .features-grid {
                    grid-template-columns: 1fr;
                }
                
                h1 {
                    font-size: 2em;
                }
                
                .container {
                    padding: 40px 20px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji">🚀</div>
            <h1>Welcome to Flask App</h1>
            <p class="subtitle">with OME Pharma News Research Blueprint</p>
            
            <div class="status">✓ System Online</div>
            
            <div class="feature-box">
                <h2>🔬 Pharma News Research Agent</h2>
                <p>
                    AI-powered pharmaceutical news research with multi-source data collection.
                    Search across PubMed, Exa, Tavily, and NewsAPI with intelligent relevance scoring.
                </p>
                <a href="/OME/" class="btn btn-primary">Launch Research Agent →</a>
            </div>
            
            <div class="features-grid">
                <div class="feature-item">
                    <h3>🤖 AI-Powered</h3>
                    <p>Smart relevance scoring and content analysis using GPT-4</p>
                </div>
                <div class="feature-item">
                    <h3>📊 Multi-Source</h3>
                    <p>Aggregates from 4+ pharmaceutical news sources</p>
                </div>
                <div class="feature-item">
                    <h3>🔄 Auto-Dedup</h3>
                    <p>Automatic deduplication of similar articles</p>
                </div>
                <div class="feature-item">
                    <h3>💾 CSV Export</h3>
                    <p>Export results and batch processing support</p>
                </div>
            </div>
            
            <div style="margin-top: 40px;">
                <a href="/OME/" class="btn btn-primary">Get Started</a>
                <a href="/OME/health" class="btn btn-secondary">Health Check</a>
            </div>
            
            <p style="margin-top: 40px; color: #95a5a6; font-size: 0.9em;">
                Flask Blueprint Demo • OME Endpoint Integration
            </p>
        </div>
    </body>
    </html>
    """

@app.route('/your-other-route')
def other_route():
    return "Your other existing endpoints work as before!"

if __name__ == '__main__':
    print("=" * 60)
    print("Flask App with OME Blueprint")
    print("=" * 60)
    print("Main app: http://localhost:5000/")
    print("OME Agent: http://localhost:5000/OME/")
    print("OME Health: http://localhost:5000/OME/health")
    print("=" * 60)
    
    app.run(host='127.0.0.1', port=5000, debug=True)

