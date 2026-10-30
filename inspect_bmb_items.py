import sys, re
import requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

for cat_name, cat_url in [
    ("DENR Administrative Orders", "https://elibrary.bmb.gov.ph/elibrary/laws-and-policies/denr-administrative-orders/"),
    ("DENR Memorandum Circulars / Orders", "https://elibrary.bmb.gov.ph/elibrary/laws-and-policies/denr-memorandum-circulars-orders/")
]:
    print(f"\n=== {cat_name} ({cat_url}) ===")
    resp = requests.get(cat_url, headers=headers, verify=False, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find all file blocks / download links
    items = []
    # Elements that contain a download link
    for a in soup.find_all('a', href=lambda h: h and '.pdf' in h.lower()):
        text = a.get_text(strip=True)
        if text.lower() == 'download':
            # Look at sibling or parent text
            parent = a.parent
            title_text = parent.get_text(' ', strip=True).replace('Download', '').strip()
        else:
            title_text = text
            
        if title_text and (title_text, a['href']) not in items:
            items.append((title_text, a['href']))

    print(f"Total items extracted: {len(items)}")
    for t, l in items[:8]:
        # Parse DAO number or DMC number
        m = re.search(r'(?:DAO|DMC|DENR\s*(?:Administrative\s*Order|Memorandum\s*Circular))?[\s_-]*((?:20\d\d|19\d\d)[-_]\d+[\w-]*)', t, re.IGNORECASE)
        num = m.group(0).strip() if m else ""
        print(f"  Title/Text: {t}")
        print(f"  Issuance No.: {num}")
        print(f"  Link: {l}\n")
