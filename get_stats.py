from pathlib import Path
import os
import pandas as pd
from datetime import datetime, timedelta
import humanize
import sqlite3

class ND2Analyzer:
    def __init__(self, base_path="/home/aaristov/Multicell", cold_storage_threshold_days=90):
        self.base_path = Path(base_path)
        self.threshold_days = cold_storage_threshold_days
        self.findings = []

    def get_file_info(self, file_path):
        stats = os.stat(file_path)
        return {
            'path': str(file_path),
            'size': stats.st_size,
            'last_access': datetime.fromtimestamp(stats.st_atime),
            'last_modified': datetime.fromtimestamp(stats.st_mtime),
            'user': file_path.parts[4]  # Assuming path structure /home/aaristov/Multicell/USER/...
        }

    def analyze_directory(self, user):
        user_path = self.base_path / user
        cutoff_date = datetime.now() - timedelta(days=self.threshold_days)
        
        for nd2_file in user_path.rglob("*.nd2"):
            info = self.get_file_info(nd2_file)
            
            if info['last_access'] < cutoff_date:
                self.findings.append(info)

    def generate_report(self):
        if not self.findings:
            return "No files found matching criteria"

        df = pd.DataFrame(self.findings)
        
        # Group by user
        user_summary = df.groupby('user').agg({
            'size': ['count', 'sum'],
            'last_access': 'min'
        }).round(2)

        total_size = df['size'].sum()
        
        report = {
            'total_files': len(df),
            'total_size': humanize.naturalsize(total_size, binary=True),
            'users_affected': len(df['user'].unique()),
            'user_details': user_summary,
            'recommendations': []
        }

        # Generate specific recommendations
        for _, row in df.iterrows():
            days_unused = (datetime.now() - row['last_access']).days
            report['recommendations'].append({
                'file': row['path'],
                'size': humanize.naturalsize(row['size'], binary=True),
                'days_unused': days_unused,
                'last_access': row['last_access'].strftime('%Y-%m-%d'),
                'priority': 'HIGH' if days_unused > 180 else 'MEDIUM'
            })

        return report

def main():
    analyzer = ND2Analyzer()
    
    # Get list of users from storage monitoring database
    with sqlite3.connect('instance/storage.db') as conn:
        users = pd.read_sql("SELECT DISTINCT folder FROM storage_data", conn)['folder'].tolist()
    
    for user in users:
        analyzer.analyze_directory(user)
    
    report = analyzer.generate_report()
    
    # Generate CSV files for each user
    for user in users:
        user_recommendations = [r for r in report['recommendations'] 
                              if user in Path(r['file']).parts]
        if user_recommendations:
            df = pd.DataFrame(user_recommendations)
            df.to_csv(f'migration_recommendations_{user}.csv', index=False)
    
    return report

if __name__ == "__main__":
    report = main()
    print(f"Found {report['total_files']} .nd2 files that can be moved to cold storage")
    print(f"Total space that can be freed: {report['total_size']}")
    print("\nBreakdown by user:")
    print(report['user_details'])
    print("\nRecommendation files have been generated for each user.")