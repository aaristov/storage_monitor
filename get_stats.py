from pathlib import Path
import os
import time
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import humanize

class ND2Analyzer:
    def __init__(self, base_path="/home/aaristov/Multicell"):
        self.base_path = Path(base_path)
        self.db_path = 'instance/storage.db'
        self.findings = []

    def get_file_info(self, file_path):
        stats = os.stat(file_path)
        return {
            'path': str(file_path),
            'size_bytes': stats.st_size,
            'creation_date': datetime.fromtimestamp(stats.st_ctime),
            'last_access': datetime.fromtimestamp(stats.st_atime),
            'last_modified': datetime.fromtimestamp(stats.st_mtime),
            'user': file_path.parts[4]
        }

    def analyze_directory(self, user):
        user_path = self.base_path / user
        
        for nd2_file in user_path.rglob("*.nd2"):
            info = self.get_file_info(nd2_file)
            self.findings.append(info)

    def save_to_database(self):
        df = pd.DataFrame(self.findings)
        with sqlite3.connect(self.db_path) as conn:
            # Clear old data
            conn.execute("DELETE FROM nd2_files")
            
            # Insert new findings
            df.to_sql('nd2_files', conn, if_exists='append', index=False)

    def generate_age_summary(self):
        now = datetime.now()
        df = pd.DataFrame(self.findings)
        
        def get_age_category(date):
            days = (now - date).days
            if days <= 30: return '1_month'
            if days <= 90: return '3_months'
            if days <= 180: return '6_months'
            return '12_plus_months'

        df['age_category'] = df['last_access'].apply(get_age_category)
        
        summary = df.groupby(['user', 'age_category']).agg({
            'size_bytes': ['count', 'sum'],
            'last_access': 'min',
            'last_modified': 'max'
        }).round(2)

        return summary

def main():
    analyzer = ND2Analyzer()
    
    # Get list of users from storage monitoring database
    with sqlite3.connect('storage.db') as conn:
        users = pd.read_sql("SELECT DISTINCT folder FROM storage_data", conn)['folder'].tolist()
    
    for user in users:
        analyzer.analyze_directory(user)
    
    # Save to database
    analyzer.save_to_database()
    
    # Generate and save summary
    summary = analyzer.generate_age_summary()
    return summary

if __name__ == "__main__":
    summary = main()
    print("ND2 analysis completed and saved to database")