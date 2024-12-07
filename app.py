from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import humanize
import pandas as pd

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///storage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TOTAL_STORAGE_CAPACITY'] = 80 * 1024**4  # 80 TB in bytes
db = SQLAlchemy(app)

# Models
class StorageData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folder = db.Column(db.String(100))
    size_bytes = db.Column(db.BigInteger)
    date = db.Column(db.DateTime)
    last_modified = db.Column(db.DateTime)

def get_latest_storage_data():
    """Get the most recent storage data for all users"""
    subquery = db.session.query(
        StorageData.folder,
        db.func.max(StorageData.date).label('max_date')
    ).group_by(StorageData.folder).subquery()
    
    return StorageData.query.join(
        subquery,
        db.and_(
            StorageData.folder == subquery.c.folder,
            StorageData.date == subquery.c.max_date
        )
    ).order_by(StorageData.size_bytes.desc()).all()

def get_user_history(username, days=30):
    """Get storage history for a specific user"""
    cutoff = datetime.now() - timedelta(days=days)
    return StorageData.query.filter(
        StorageData.folder == username,
        StorageData.date >= cutoff
    ).order_by(StorageData.date).all()

def get_total_storage():
    """Get total storage used across all users"""
    latest = get_latest_storage_data()
    return sum(entry.size_bytes for entry in latest)

def get_storage_status():
    """Get storage usage status and warnings"""
    total_used = get_total_storage()
    capacity = app.config['TOTAL_STORAGE_CAPACITY']
    usage_percent = (total_used / capacity) * 100
    
    status = {
        'total_used': total_used,
        'capacity': capacity,
        'usage_percent': usage_percent,
        'available': capacity - total_used,
        'warning_level': 'normal'
    }
    
    if usage_percent >= 90:
        status['warning_level'] = 'critical'
    elif usage_percent >= 80:
        status['warning_level'] = 'warning'
    elif usage_percent >= 70:
        status['warning_level'] = 'notice'
        
    return status

def get_nd2_summary():
    """Get summary of ND2 files by age categories"""
    query = """
    SELECT 
        user,
        CASE 
            WHEN julianday('now') - julianday(last_access) <= 30 THEN '1_month'
            WHEN julianday('now') - julianday(last_access) <= 90 THEN '3_months'
            WHEN julianday('now') - julianday(last_access) <= 180 THEN '6_months'
            ELSE '12_plus_months'
        END as age_category,
        COUNT(*) as file_count,
        SUM(size_bytes) as total_size
    FROM nd2_files
    GROUP BY user, age_category
    ORDER BY user, age_category
    """
    
    try:
        with db.engine.connect() as conn:
            return pd.read_sql(query, conn)
    except:
        return pd.DataFrame()

def get_user_nd2_stats(username):
    """Get ND2 statistics for a specific user"""
    query = """
    SELECT 
        CASE 
            WHEN julianday('now') - julianday(last_access) <= 30 THEN '1_month'
            WHEN julianday('now') - julianday(last_access) <= 90 THEN '3_months'
            WHEN julianday('now') - julianday(last_access) <= 180 THEN '6_months'
            ELSE '12_plus_months'
        END as age_category,
        COUNT(*) as file_count,
        SUM(size_bytes) as total_size,
        MIN(last_access) as oldest_access,
        MAX(last_access) as newest_access
    FROM nd2_files
    WHERE user = ?
    GROUP BY age_category
    ORDER BY age_category
    """
    
    try:
        with db.engine.connect() as conn:
            stats = pd.read_sql(query, conn, params=[username])
            # Convert to dictionary for easier template handling
            return stats.to_dict('records')
    except:
        return []

# Routes
@app.route('/')
def index():
    users = get_latest_storage_data()
    storage_status = get_storage_status()
    nd2_summary = get_nd2_summary()
    
    return render_template('index.html', 
                         users=users,
                         storage_status=storage_status,
                         nd2_summary=nd2_summary,
                         humanize=humanize)

@app.route('/api/user/<username>/history')
def user_history_api(username):
    """API endpoint for user storage history"""
    history = get_user_history(username)
    return jsonify([{
        'date': entry.date.isoformat(),
        'size': entry.size_bytes,
        'size_human': humanize.naturalsize(entry.size_bytes, binary=True)
    } for entry in history])

@app.route('/user/<username>')
def user_detail(username):
    user_data = StorageData.query.filter_by(folder=username).order_by(StorageData.date.desc()).first()
    history = get_user_history(username)
    storage_status = get_storage_status()
    nd2_stats = get_user_nd2_stats(username)
    
    return render_template('user_detail.html',
                         user=user_data,
                         history=history,
                         storage_status=storage_status,
                         nd2_stats=nd2_stats,
                         humanize=humanize)

if __name__ == '__main__':
    app.run(debug=True)
