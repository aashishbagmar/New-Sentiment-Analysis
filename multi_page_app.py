# Updated app.py with Analysis History Storage

import os
import os as _os
_os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests
import pandas as pd
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
import re
from functools import wraps
import json

# Import our enhanced modules
from enhanced_stock_info import get_comprehensive_stock_info, format_market_cap, format_employee_count
from correlation_engine import StockCorrelationEngine

# Load API key
load_dotenv()
API_KEY = os.getenv("NEWS_API_KEY")
if not API_KEY:
    raise ValueError("NEWS_API_KEY not found in .env file.")

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))

# MySQL Configuration
MYSQL_CONFIG = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'port': int(os.getenv("MYSQL_PORT", 3306)),
    'user': os.getenv("MYSQL_USER", "root"),
    'password': os.getenv("MYSQL_PASSWORD", ""),
    'database': os.getenv("MYSQL_DATABASE", "stock_sentiment_db"),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': True
}

def get_db_connection():
    """Create and return a MySQL database connection."""
    try:
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_db():
    """Initialize the MySQL database with users and watchlists tables."""
    connection = get_db_connection()
    if connection is None:
        raise Exception("Failed to connect to MySQL database")
    
    cursor = connection.cursor()
    
    try:
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']}")
        cursor.execute(f"USE {MYSQL_CONFIG['database']}")
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Create watchlists table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlists (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                company_name VARCHAR(100) NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE KEY unique_user_company (user_id, company_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Create analysis_history table for storing complete analyses
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                session_id VARCHAR(100) NOT NULL,
                company_name VARCHAR(100) NOT NULL,
                ticker_symbol VARCHAR(20),
                analysis_date DATE NOT NULL,
                overall_sentiment VARCHAR(50),
                total_articles INT DEFAULT 0,
                positive_count INT DEFAULT 0,
                negative_count INT DEFAULT 0,
                neutral_count INT DEFAULT 0,
                sector VARCHAR(100),
                industry VARCHAR(100),
                market_cap BIGINT DEFAULT 0,
                country VARCHAR(100),
                correlation_summary JSON,
                news_data JSON,
                stock_info JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
                INDEX idx_user_id (user_id),
                INDEX idx_session_id (session_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        connection.commit()
        print("Database tables created successfully")
        
    except Error as e:
        print(f"Error creating tables: {e}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()

# Initialize database on startup
try:
    init_db()
except Exception as e:
    print(f"Failed to initialize database: {e}")

# Models (lazy-loaded on first request)
sentiment_analyzer = None
sbert_model = None
correlation_engine = None

def load_models():
    global sentiment_analyzer, sbert_model, correlation_engine
    if sentiment_analyzer is None:
        sentiment_analyzer = pipeline(
            "sentiment-analysis",
            model="distilbert/distilbert-base-uncased-finetuned-sst-2-english"
        )
    if sbert_model is None:
        sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
    if correlation_engine is None:
        correlation_engine = StockCorrelationEngine()

# Authentication helper functions
def login_required(f):
    """Decorator to require login for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def validate_password(password):
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, "Password is valid"

def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Database helper functions
def get_user_by_username(username):
    """Get user by username."""
    connection = get_db_connection()
    if connection is None:
        return None
    
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()
    return user

def get_user_by_email(email):
    """Get user by email."""
    connection = get_db_connection()
    if connection is None:
        return None
    
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()
    return user

def create_user(username, email, password, full_name):
    """Create a new user."""
    connection = get_db_connection()
    if connection is None:
        return None
    
    cursor = connection.cursor()
    password_hash = generate_password_hash(password)
    
    try:
        cursor.execute(
            'INSERT INTO users (username, email, password_hash, full_name) VALUES (%s, %s, %s, %s)',
            (username, email, password_hash, full_name)
        )
        user_id = cursor.lastrowid
        connection.commit()
        return user_id
    except Error as e:
        print(f"Error creating user: {e}")
        connection.rollback()
        return None
    finally:
        cursor.close()
        connection.close()

def get_user_watchlist(user_id):
    """Get user's watchlist."""
    connection = get_db_connection()
    if connection is None:
        return []
    
    cursor = connection.cursor()
    cursor.execute('SELECT company_name FROM watchlists WHERE user_id = %s', (user_id,))
    watchlist = [row[0] for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return watchlist

def add_to_user_watchlist(user_id, company):
    """Add company to user's watchlist."""
    connection = get_db_connection()
    if connection is None:
        return False
    
    cursor = connection.cursor()
    try:
        cursor.execute(
            'INSERT INTO watchlists (user_id, company_name) VALUES (%s, %s)',
            (user_id, company)
        )
        connection.commit()
        success = True
    except Error:
        success = False  # Company already in watchlist or other error
        connection.rollback()
    finally:
        cursor.close()
        connection.close()
    return success

def remove_from_user_watchlist(user_id, company):
    """Remove company from user's watchlist."""
    connection = get_db_connection()
    if connection is None:
        return False
    
    cursor = connection.cursor()
    try:
        cursor.execute(
            'DELETE FROM watchlists WHERE user_id = %s AND company_name = %s',
            (user_id, company)
        )
        connection.commit()
        success = True
    except Error:
        success = False
        connection.rollback()
    finally:
        cursor.close()
        connection.close()
    return success

# Analysis History Functions
def save_analysis_to_history(session_id, company_name, ticker_symbol, analysis_date, 
                            news_data, overall_signal, stock_info):
    """Save complete analysis to history."""
    connection = get_db_connection()
    if connection is None:
        return False
    
    cursor = connection.cursor()
    
    try:
        # Calculate sentiment counts
        positive_count = len([item for item in news_data if item.get('sentiment') == 'Positive'])
        negative_count = len([item for item in news_data if item.get('sentiment') == 'Negative'])
        neutral_count = len([item for item in news_data if item.get('sentiment') == 'Neutral'])
        
        # Prepare correlation summary
        correlation_summary = {}
        if stock_info and stock_info.get('correlation_analysis'):
            correlation_summary = {
                'total_analyzed': stock_info['correlation_analysis']['total_analyzed'],
                'average_correlation': stock_info['correlation_analysis']['average_correlation'],
                'market_influence': stock_info['correlation_analysis']['market_influence']
            }
        
        cursor.execute('''
            INSERT INTO analysis_history 
            (user_id, session_id, company_name, ticker_symbol, analysis_date, overall_sentiment,
             total_articles, positive_count, negative_count, neutral_count, sector, industry,
             market_cap, country, correlation_summary, news_data, stock_info)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            session.get('user_id'),
            session_id,
            company_name,
            ticker_symbol,
            analysis_date,
            overall_signal,
            len(news_data),
            positive_count,
            negative_count,
            neutral_count,
            stock_info.get('sector', '') if stock_info else '',
            stock_info.get('industry', '') if stock_info else '',
            stock_info.get('market_cap', 0) if stock_info else 0,
            stock_info.get('country', '') if stock_info else '',
            json.dumps(correlation_summary),
            json.dumps(news_data),
            json.dumps(stock_info) if stock_info else '{}'
        ))
        
        connection.commit()
        return True
        
    except Error as e:
        print(f"Error saving analysis to history: {e}")
        connection.rollback()
        return False
    finally:
        cursor.close()
        connection.close()

def get_user_analysis_history(user_id, limit=20):
    """Get user's analysis history."""
    connection = get_db_connection()
    if connection is None:
        return []
    
    cursor = connection.cursor()
    cursor.execute('''
        SELECT id, company_name, ticker_symbol, analysis_date, overall_sentiment,
               total_articles, sector, industry, market_cap, country, created_at
        FROM analysis_history 
        WHERE user_id = %s OR user_id IS NULL
        ORDER BY created_at DESC 
        LIMIT %s
    ''', (user_id, limit))
    
    results = cursor.fetchall()
    cursor.close()
    connection.close()
    
    history = []
    for row in results:
        history.append({
            'id': row[0],
            'company_name': row[1],
            'ticker_symbol': row[2],
            'analysis_date': row[3].strftime('%Y-%m-%d') if row[3] else '',
            'overall_sentiment': row[4],
            'total_articles': row[5],
            'sector': row[6],
            'industry': row[7],
            'market_cap': row[8],
            'country': row[9],
            'created_at': row[10].strftime('%B %d, %Y') if row[10] else ''
        })
    
    return history

def get_analysis_by_id(analysis_id, user_id):
    """Get specific analysis by ID."""
    connection = get_db_connection()
    if connection is None:
        return None
    
    cursor = connection.cursor()
    cursor.execute('''
        SELECT * FROM analysis_history 
        WHERE id = %s AND (user_id = %s OR user_id IS NULL)
    ''', (analysis_id, user_id))
    
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if result:
        return {
            'id': result[0],
            'company_name': result[3],
            'ticker_symbol': result[4],
            'analysis_date': result[5],
            'overall_sentiment': result[6],
            'total_articles': result[7],
            'positive_count': result[8],
            'negative_count': result[9],
            'neutral_count': result[10],
            'sector': result[11],
            'industry': result[12],
            'market_cap': result[13],
            'country': result[14],
            'correlation_summary': json.loads(result[15]) if result[15] else {},
            'news_data': json.loads(result[16]) if result[16] else [],
            'stock_info': json.loads(result[17]) if result[17] else {}
        }
    
    return None

# Session helper functions
def save_analysis_session(company, analysis_date, ticker_symbol=None):
    """Save analysis session for multi-page navigation."""
    session_id = session.get('session_id', os.urandom(16).hex())
    session['session_id'] = session_id
    session['last_company'] = company
    session['last_date'] = analysis_date
    session['last_ticker'] = ticker_symbol
    return session_id

def get_current_analysis():
    """Get current analysis session data."""
    return {
        'company': session.get('last_company'),
        'date': session.get('last_date'),
        'ticker': session.get('last_ticker')
    }

def get_date_range(time_period):
    """Compute date range for NewsAPI and analysis_date for DB based on time period or specific date."""
    now = datetime.now(timezone.utc)

    MAX_HISTORY_DAYS = 180  # Limit to 180 days back for free API plan

    # Check if time_period is a specific date (YYYY-MM-DD format)
    try:
        specific_date = datetime.strptime(time_period, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        from_date = specific_date.replace(hour=0, minute=0, second=0, microsecond=0)
        to_date = specific_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        analysis_date = specific_date.date().strftime("%Y-%m-%d")
        return from_date.isoformat(), to_date.isoformat(), analysis_date
    except ValueError:
        # Not a specific date, treat as time period
        pass

    # Handle predefined time periods
    if time_period == "last_hour":
        from_date = now - timedelta(hours=1)
        to_date = now
        analysis_date = now.date().strftime("%Y-%m-%d")
    elif time_period == "today":
        from_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        to_date = now
        analysis_date = now.date().strftime("%Y-%m-%d")
    elif time_period == "this_week":
        from_date = now - timedelta(days=7)
        to_date = now
        analysis_date = now.date().strftime("%Y-%m-%d")
    elif time_period == "this_month":
        from_date = now - timedelta(days=30)
        to_date = now
        analysis_date = now.date().strftime("%Y-%m-%d")
    else:
        raise ValueError(f"Invalid time period: {time_period}")

    return from_date.isoformat(), to_date.isoformat(), analysis_date

# Session-based watchlist (fallback for non-authenticated users)
def get_watchlist():
    if 'user_id' in session:
        return get_user_watchlist(session['user_id'])
    return session.get("watchlist", [])

def add_to_watchlist(company):
    if 'user_id' in session:
        return add_to_user_watchlist(session['user_id'], company)
    else:
        wl = session.get("watchlist", [])
        if company not in wl:
            wl.append(company)
            session["watchlist"] = wl
        return True

def remove_from_watchlist(company):
    if 'user_id' in session:
        return remove_from_user_watchlist(session['user_id'], company)
    else:
        wl = session.get("watchlist", [])
        if company in wl:
            wl.remove(company)
            session["watchlist"] = wl
        return True

# Core analysis functions
def fetch_news_only(company, from_date_str, to_date_str):
    """Fetch only news articles without sentiment analysis."""
    load_models()
    
    company_embedding = sbert_model.encode(company, convert_to_tensor=True)
    url = "https://newsapi.org/v2/everything"
    page = 1
    page_size = 100
    all_articles = []
    
    max_articles = 100  # Limit to 100 results max for free API plan
    while len(all_articles) < max_articles:
        params = {
            "q": f'"{company}"',
            "apiKey": API_KEY,
            "language": "en",
            "from": from_date_str,
            "to": to_date_str,
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "page": page
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            # Log full response content for debugging
            print(f"News API error {response.status_code}: {response.text}")
            return [], f"Error fetching news: {response.status_code} - {response.text}"
        data = response.json()
        articles = data.get("articles", [])
        if not articles:
            break
        all_articles.extend(articles)
        if len(all_articles) >= max_articles:
            all_articles = all_articles[:max_articles]
            break
        # Stop pagination after first page to avoid exceeding 100 results limit
        break
        # if page * page_size >= data.get("totalResults", 0):
        #     break
        # page += 1
        # time.sleep(1)
    
    # SBERT semantic filtering
    SIMILARITY_THRESHOLD = 0.3
    filtered_articles = []
    for article in all_articles:
        title = article.get("title", "")
        if not title:
            continue
        title_embedding = sbert_model.encode(title, convert_to_tensor=True)
        similarity = util.cos_sim(company_embedding, title_embedding).item()
        if similarity >= SIMILARITY_THRESHOLD:
            # Format article data
            raw_date = article["publishedAt"]
            try:
                date_obj = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                formatted_date = date_obj.strftime("%d-%m-%Y")
                formatted_time = date_obj.strftime("%H:%M")
            except Exception:
                formatted_date = raw_date
                formatted_time = ""
            
            filtered_articles.append({
                "title": title,
                "date": formatted_date,
                "time": formatted_time,
                "reference": article["source"]["name"],
                "description": article.get("description", "")[:200] + "..." if article.get("description") else "",
                "url": article.get("url", ""),
                "image": article.get("urlToImage", ""),
                "author": article.get("author", "Unknown")
            })
    
    return filtered_articles, None

def analyze_sentiment_only(company, from_date_str, to_date_str):
    """Perform sentiment analysis on news articles."""
    load_models()
    
    articles, error = fetch_news_only(company, from_date_str, to_date_str)
    if error:
        return [], None, 0, error
    
    # Sentiment analysis
    news_data = []
    for article in articles:
        title = article["title"]
        sentiment_label = sentiment_analyzer(title)[0]["label"].upper()
        if sentiment_label == "POSITIVE":
            sentiment_signal = "Positive"
        elif sentiment_label == "NEGATIVE":
            sentiment_signal = "Negative"
        else:
            sentiment_signal = "Neutral"
        
        article["sentiment"] = sentiment_signal
        news_data.append(article)
    
    # Calculate overall sentiment
    df = pd.DataFrame([{"sentiment": article["sentiment"]} for article in news_data])
    if df.empty:
        return [], None, 0, None
    
    positive = (df["sentiment"] == "Positive").sum()
    negative = (df["sentiment"] == "Negative").sum()
    if positive > negative:
        overall_signal = "Positive"
    elif negative > positive:
        overall_signal = "Negative"
    else:
        overall_signal = "Neutral"
    
    return news_data, overall_signal, len(news_data), None

# Authentication Routes
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        full_name = request.form["full_name"].strip()
        
        # Validation
        if not all([username, email, password, confirm_password, full_name]):
            flash("All fields are required", "error")
            return render_template("register.html")
        
        if len(username) < 3:
            flash("Username must be at least 3 characters long", "error")
            return render_template("register.html")
        
        if not validate_email(email):
            flash("Invalid email format", "error")
            return render_template("register.html")
        
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("register.html")
        
        is_valid, message = validate_password(password)
        if not is_valid:
            flash(message, "error")
            return render_template("register.html")
        
        # Check if user already exists
        if get_user_by_username(username):
            flash("Username already exists", "error")
            return render_template("register.html")
        
        if get_user_by_email(email):
            flash("Email already registered", "error")
            return render_template("register.html")
        
        # Create user
        user_id = create_user(username, email, password, full_name)
        if user_id:
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Registration failed. Please try again.", "error")
            return render_template("register.html")
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        
        if not username or not password:
            flash("Username and password are required", "error")
            return render_template("login.html")
        
        user = get_user_by_username(username)
        if user and check_password_hash(user[3], password):  # user[3] is password_hash
            session["user_id"] = user[0]  # user[0] is id
            session["username"] = user[1]  # user[1] is username
            session["full_name"] = user[4]  # user[4] is full_name
            flash(f"Welcome back, {user[4]}!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")
            return render_template("login.html")
    
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out successfully", "info")
    return redirect(url_for("login"))

# Main dashboard route (search form)
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        company = request.form.get("company", "").strip()  # Use .get() instead of ["company"]
        raw_date = request.form.get("date", "")          # hidden date (may be empty)
        timeframe_selection = request.form.get('analysis_timeframe', '')

        # Normalize and choose a time parameter: prefer explicit timeframe key,
        # otherwise fall back to the hidden date string (which may be YYYY-MM-DD).
        date_input = (timeframe_selection or raw_date).strip()
        
        # Handle add to watchlist requests (without date)
        if "add_watchlist" in request.form and company:
            if add_to_watchlist(company):
                flash(f"{company} added to your watchlist!", "success")
            else:
                flash(f"{company} is already in your watchlist", "info")
            
            # If no date provided, just return to index
            if not date_input:
                recent_analyses = []
                if 'user_id' in session:
                    recent_analyses = get_user_analysis_history(session['user_id'], limit=5)
                
                return render_template("index.html", 
                                       watchlist=get_watchlist(),
                                       recent_analyses=recent_analyses,
                                       user_name=session.get("full_name"),
                                       )
        
        # Handle regular analysis requests
        if company and date_input:
            try:
                from_d, to_d, analysis_date = get_date_range(date_input)
            except Exception as e:
                flash(str(e), 'error')
                return render_template('index.html', watchlist=get_watchlist(), recent_analyses=[], user_name=session.get('full_name'))

            stock_info = get_comprehensive_stock_info(company)
            session['last_date'] = analysis_date
            session['last_time_period'] = date_input
            session_id = save_analysis_session(company, analysis_date, stock_info.get('ticker'))

            # Redirect to latest_news with explicit from/to ISO datetimes so the news page
            # can immediately fetch the correct interval (avoids any ambiguity)
            return redirect(url_for('latest_news', **{'from': from_d, 'to': to_d}))
        
        # Handle missing fields
        if not company:
            flash("Please enter a company name", "error")
        elif not date_input:
            flash("Please select a time period for analysis", "error")
    
    # GET request or error case
    recent_analyses = []
    if 'user_id' in session:
        recent_analyses = get_user_analysis_history(session['user_id'], limit=5)
    
    return render_template("index.html", 
                           watchlist=get_watchlist(),
                           recent_analyses=recent_analyses,
                           user_name=session.get("full_name"),
                           datetime = datetime)

# PAGE 1: Latest News Articles
@app.route("/latest-news")
def latest_news():
    current_analysis = get_current_analysis()
    
    if not current_analysis['company'] or not current_analysis['date']:
        flash("Please perform a stock analysis first", "error")
        return redirect(url_for('index'))
    
    company = current_analysis['company']
    analysis_date = current_analysis['date']
    time_period = session.get('last_time_period')
    
    # Allow overriding the timeframe via query params (from/to as ISO datetimes)
    from_param = request.args.get('from')
    to_param = request.args.get('to')
    if from_param and to_param:
        try:
            # Validate ISO datetimes
            from_dt = datetime.fromisoformat(from_param.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(to_param.replace('Z', '+00:00'))
            from_d = from_dt.astimezone(timezone.utc).isoformat()
            to_d = to_dt.astimezone(timezone.utc).isoformat()
        except Exception:
            flash("Invalid date range provided", "error")
            return redirect(url_for('latest_news'))
    elif time_period:
        from_d, to_d, _ = get_date_range(time_period)
    else:
        # Fallback for legacy sessions
        try:
            from_date = datetime.strptime(analysis_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            to_date = from_date.replace(hour=23, minute=59, second=59)
            from_d = from_date.isoformat()
            to_d = to_date.isoformat()
        except ValueError:
            flash("Invalid date format in session", "error")
            return redirect(url_for('index'))
    
    # Fetch news articles with sentiment
    results, overall_signal, total, error = analyze_sentiment_only(
        company, 
        from_d, 
        to_d
    )
    
    # Get stock info for saving to history
    stock_info = get_comprehensive_stock_info(company)
    
    # Save complete analysis to history
    if results and not error and 'user_id' in session:
        save_analysis_to_history(
            session.get('session_id'),
            company,
            stock_info.get('ticker') if stock_info else None,
            analysis_date,
            results,
            overall_signal,
            stock_info
        )
    
    return render_template("latest_news.html",
                           results=results,
                           overall_signal=overall_signal,
                           total=total,
                           error=error,
                           company=company,
                           date_input=analysis_date,
                           from_date=from_d,
                           to_date=to_d,
                           user_name=session.get("full_name"))

# PAGE 2: Stock Correlations (Which other stocks they affect)
@app.route("/stock-correlations")
def stock_correlations():
    current_analysis = get_current_analysis()
    
    if not current_analysis['company']:
        flash("Please perform a stock analysis first", "error")
        return redirect(url_for('index'))
    
    # Get comprehensive stock info with correlations
    stock_info = get_comprehensive_stock_info(current_analysis['company'])
    
    return render_template("stock_correlations.html",
                           stock_info=stock_info,
                           company=current_analysis['company'],
                           user_name=session.get("full_name"))

# PAGE 3: Stock Domain/Sector Information
@app.route("/stock-domain")
def stock_domain():
    current_analysis = get_current_analysis()
    
    if not current_analysis['company']:
        flash("Please perform a stock analysis first", "error")
        return redirect(url_for('index'))
    
    # Get comprehensive stock info
    stock_info = get_comprehensive_stock_info(current_analysis['company'])
    
    return render_template("stock_domain.html",
                           stock_info=stock_info,
                           company=current_analysis['company'],
                           user_name=session.get("full_name"))

# Analysis History Routes
@app.route("/analysis-history")
@login_required
def analysis_history():
    """Display user's analysis history."""
    history = get_user_analysis_history(session['user_id'], limit=50)
    
    return render_template("analysis_history.html",
                           history=history,
                           user_name=session.get("full_name"))

@app.route("/view-analysis/<int:analysis_id>")
@login_required
def view_analysis(analysis_id):
    """View a specific historical analysis."""
    analysis = get_analysis_by_id(analysis_id, session['user_id'])
    
    if not analysis:
        flash("Analysis not found", "error")
        return redirect(url_for('analysis_history'))
    
    return render_template("view_analysis.html",
                           analysis=analysis,
                           user_name=session.get("full_name"))

@app.route("/download_analysis/<int:analysis_id>")
@login_required
def download_analysis(analysis_id):
    """Download a specific analysis report as JSON."""
    analysis = get_analysis_by_id(analysis_id, session['user_id'])
    
    if not analysis:
        flash("Analysis not found", "error")
        return redirect(url_for('analysis_history'))
    
    # Prepare report data
    report_data = {
        "analysis_id": analysis['id'],
        "company_name": analysis['company_name'],
        "ticker_symbol": analysis['ticker_symbol'],
        "analysis_date": analysis['analysis_date'],
        "overall_sentiment": analysis['overall_sentiment'],
        "total_articles": analysis['total_articles'],
        "sentiment_counts": {
            "positive": analysis['positive_count'],
            "negative": analysis['negative_count'],
            "neutral": analysis['neutral_count']
        },
        "sector": analysis['sector'],
        "industry": analysis['industry'],
        "market_cap": analysis['market_cap'],
        "country": analysis['country'],
        "correlation_summary": analysis['correlation_summary'],
        "news_data": analysis['news_data'][:10],  # Limit news to top 10 for file size
        "stock_info": analysis['stock_info'],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Create JSON response for download
    from flask import make_response
    response = make_response(json.dumps(report_data, indent=2, default=str))
    response.headers["Content-Disposition"] = f"attachment; filename=analysis_{analysis_id}_{analysis['company_name'].replace(' ', '_')}.json"
    response.headers["Content-Type"] = "application/json"
    
    return response

@app.route("/watchlist", methods=["GET", "POST"])
def watchlist():
    wl = get_watchlist()
    all_results = []
    
    if not wl:
        return render_template("watchlist.html", 
                             error="Your watchlist is empty.", 
                             results=[],
                             user_name=session.get("full_name"))
    
    date_input = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    from_d, to_d, _ = get_date_range(date_input)
    for comp in wl:
        results, overall_signal, total, _ = analyze_sentiment_only(comp, from_d, to_d)
        if isinstance(results, list):  # Only add if no error
            for r in results:
                r["company"] = comp
                all_results.append(r)
    
    return render_template("watchlist.html", 
                         results=all_results, 
                         date_input=date_input, 
                         watchlist=wl,
                         user_name=session.get("full_name"))

@app.route("/remove_from_watchlist", methods=["POST"])
def remove_watchlist():
    comp = request.form.get("company")
    if comp:
        remove_from_watchlist(comp)
        flash(f"{comp} removed from your watchlist", "info")
    return redirect(url_for("watchlist"))

# API endpoint for correlation analysis
@app.route("/api/correlation/<ticker>")
def get_correlation_analysis(ticker):
    """API endpoint to get correlation analysis for a specific ticker."""
    try:
        load_models()
        
        # Get stock info first to determine sector
        stock_info = get_comprehensive_stock_info(ticker)
        
        if stock_info.get('correlation_analysis'):
            return jsonify({
                "success": True,
                "data": {
                    "ticker": ticker,
                    "correlation_analysis": stock_info['correlation_analysis'],
                    "related_stocks": stock_info['related_stocks']
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Could not perform correlation analysis"
            })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/add-to-watchlist", methods=["POST"])
@login_required
def add_to_watchlist_api():
    """API endpoint to add company to watchlist."""
    try:
        company = request.form.get("company", "").strip()
        
        if not company:
            return jsonify({
                "success": False,
                "message": "Company name is required"
            }), 400
        
        success = add_to_watchlist(company)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"{company} added to your watchlist!"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"{company} is already in your watchlist"
            })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error adding to watchlist. Please try again."
        }), 500



@app.route("/profile")
@login_required
def profile():
    """User profile page."""
    connection = get_db_connection()
    if connection is None:
        return redirect(url_for("login"))
    
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM users WHERE id = %s', (session["user_id"],))
    user = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if user:
        user_data = {
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'full_name': user[4],
            'created_at': str(user[5]) if user[5] else 'Unknown'
        }
        watchlist_count = len(get_user_watchlist(session["user_id"]))
        analysis_count = len(get_user_analysis_history(session["user_id"], limit=1000))
        
        return render_template("profile.html", 
                             user=user_data, 
                             watchlist_count=watchlist_count,
                             analysis_count=analysis_count)
    
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)