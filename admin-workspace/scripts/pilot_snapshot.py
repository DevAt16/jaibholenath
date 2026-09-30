"""Read the public discovery CSV; no API calls or production database access."""
import csv
import json
from pathlib import Path

path = Path(__file__).resolve().parents[2] / 'frontend/public/real-reports/candidate_review.csv'
with path.open(encoding='utf-8', newline='') as source:
    rows = [row for row in csv.DictReader(source)
            if row['state'] == 'Madhya Pradesh'
            and row['district'] in {'Ujjain', 'Khandwa', 'Gwalior'}]
if len(rows) > 2000:
    raise SystemExit('Pilot exceeds the 2,000-row safe seed limit')
print(json.dumps(rows, ensure_ascii=False))
