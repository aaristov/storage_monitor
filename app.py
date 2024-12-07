from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import humanize
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
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

# Data access functions
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

# Import data from existing SQLite database
def import_existing_data():
    """Import data from the existing storage_data table"""
    try:
        source_conn = sqlite3.connect('../storage_data.db')  # Update path as needed
        query = "SELECT folder, size_bytes, date, last_modified FROM storage_data"
        df = pd.read_sql_query(query, source_conn)
        source_conn.close()

        for _, row in df.iterrows():
            storage_entry = StorageData(
                folder=row['folder'],
                size_bytes=row['size_bytes'],
                date=datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S.%f'),
                last_modified=datetime.strptime(row['last_modified'], '%Y-%m-%d %H:%M:%S.%f')
            )
            db.session.add(storage_entry)
        
        db.session.commit()
        print("Data imported successfully")
    except Exception as e:
        print(f"Error importing data: {e}")

# Routes
@app.route('/')
def index():
    users = get_latest_storage_data()
    storage_status = get_storage_status()
    return render_template('index.html', 
                         users=users,
                         storage_status=storage_status,
                         humanize=humanize)

@app.route('/api/user/<username>/history')
def user_history(username):
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
    return render_template('user_detail.html',
                         user=user_data,
                         history=history,
                         storage_status=storage_status,
                         humanize=humanize)

if __name__ == '__main__':
    app.run(debug=True)
