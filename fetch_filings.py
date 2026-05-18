import requests
import sys
sys.path.insert(0, '/Users/Jayal/Desktop/insider-moniter')

headers = {
    "User-Agent": "Jayal insider-monitor jayal@email.com"
}

def get_recent_filings():
    url = "https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&forms=4&dateRange=custom&startdt=2025-01-01&enddt=2025-12-31"
    response = requests.get(url, headers=headers)
    data = response.json()
    return data["hits"]["hits"]

def get_filing_details(accession_no):
    # Format accession number for URL
    acc_formatted = accession_no.replace("-", "")
    cik = acc_formatted[:10].lstrip("0")
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=10&search_text="
    return url

filings = get_recent_filings()

print(f"{'Company':<40} {'Filed':<12} {'Accession No':<25}")
print("-" * 80)

for filing in filings[:1]:
    source = filing["_source"]
    print("Available fields:")
    for key, value in source.items():
        print(f"  {key}: {value}")