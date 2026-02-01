# sentiment-saas/app.py
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask import send_from_directory
from transformers import pipeline
import datetime
import secrets
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'  # Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sentiment.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Load AI model (this might take a while on first run)
try:
    sentiment_analyzer = pipeline('sentiment-analysis')
    print("AI model loaded successfully!")
except Exception as e:
    print(f"Error loading AI model: {e}")
    sentiment_analyzer = None

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    credits = db.Column(db.Integer, default=100)  # Starting credits
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationship with API keys and usage
    api_keys = db.relationship('APIKey', backref='user', lazy=True)
    usage_records = db.relationship('Usage', backref='user', lazy=True)

class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Usage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    credits_used = db.Column(db.Integer, default=1)

# Initialize database
with app.app_context():
    db.create_all()

# User loader function
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
    'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']  # In production, hash this!
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return "Username already exists"
        
        if User.query.filter_by(email=email).first():
            return "Email already exists"
        
        # Create new user
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('dashboard'))
        
        return "Invalid credentials"
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get the 5 most recent usage records
    recent_usage = Usage.query.filter_by(user_id=current_user.id).order_by(Usage.timestamp.desc()).limit(5).all()
    return render_template('dashboard.html', user=current_user, recent_usage=recent_usage)

@app.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():
    if request.method == 'POST':
        text = request.form['text']
        
        # Check if user has enough credits
        if current_user.credits < 1:
            return "Not enough credits. Please purchase more."
        
        # Check if AI model is loaded
        if not sentiment_analyzer:
            return "AI service temporarily unavailable. Please try again later."
        
        # Analyze sentiment
        result = sentiment_analyzer(text)[0]
        
        # Deduct credit and record usage
        current_user.credits -= 1
        usage = Usage(user_id=current_user.id, endpoint='web_analyze', credits_used=1)
        db.session.add(usage)
        db.session.commit()
        
        return render_template('analyze.html', result=result, text=text)
    
    return render_template('analyze.html')

@app.route('/api/docs')
@login_required
def api_docs():
    return render_template('api.html')

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    # Check for API key
    api_key = request.headers.get('Authorization')
    if not api_key:
        return jsonify({'error': 'API key required'}), 401
    
    # Validate API key
    key_record = APIKey.query.filter_by(key=api_key).first()
    if not key_record:
        return jsonify({'error': 'Invalid API key'}), 401
    
    user = key_record.user
    
    # Check if user has enough credits
    if user.credits < 1:
        return jsonify({'error': 'Not enough credits'}), 402
    
    # Check if AI model is loaded
    if not sentiment_analyzer:
        return jsonify({'error': 'AI service temporarily unavailable'}), 503
    
    # Get text from request
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Text field required'}), 400
    
    text = data['text']
    
    # Analyze sentiment
    result = sentiment_analyzer(text)[0]
    
    # Deduct credit and record usage
    user.credits -= 1
    usage = Usage(user_id=user.id, endpoint='api_analyze', credits_used=1)
    db.session.add(usage)
    db.session.commit()
    
    return jsonify({
        'text': text,
        'sentiment': result['label'],
        'confidence': result['score'],
        'credits_remaining': user.credits
    })

@app.route('/api/generate_key', methods=['POST'])
@login_required
def generate_api_key():
    # Generate a random API key
    new_key = secrets.token_urlsafe(32)
    
    # Save to database
    api_key = APIKey(key=new_key, user_id=current_user.id)
    db.session.add(api_key)
    db.session.commit()
    
    return jsonify({'api_key': new_key})

if __name__ == '__main__':
    app.run(debug=True)