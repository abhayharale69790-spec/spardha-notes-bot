import json
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("data/discovered_channels.json", encoding="utf-8") as f:
    data = json.load(f)

# Sort by pdf_count_sample desc, pdf_yield_pct desc
data.sort(key=lambda x: (x["pdf_count_sample"], x["pdf_yield_pct"]), reverse=True)
top50 = data[:50]

by_cat = {}
for c in top50:
    by_cat.setdefault(c["category"], []).append(c)

category_order = [
    "MPSC", "POLICE_BHARTI", "SARAL_SEVA", "SSC", "BANKING",
    "UPSC", "JEE", "NEET", "NCERT", "BOARD_10_12", "GENERAL"
]

total_idx = 1
for cat in category_order:
    items = by_cat.get(cat, [])
    if not items:
        continue
    print(f"\n#### 🏛️ Exam Category: `#{cat}` ({len(items)} Discovered Channels)")
    print("| # | Channel Username | PDFs in 100-Msg Sample | Yield % | Est. Yield | Latest Msg (Date) | Duplicate / Related Check | Source Link | Official Title |")
    print("| :-: | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- |")
    for item in items:
        uname = item['username']
        title = item['title'].replace('|', '/')
        yield_str = f"{item['pdf_count_sample']}/100"
        pct_str = f"{item['pdf_yield_pct']}%"
        est = item['estimated_yield']
        latest_str = f"#{item['latest_msg_id']} ({item['latest_date']})"
        rel = item['related_channel'].replace('|', '/')
        link = f"[{uname}]({item['source_url']})"
        print(f"| **{total_idx}** | **`{uname}`** | **{yield_str}** | **{pct_str}** | {est} | `{latest_str}` | *{rel}* | {link} | {title} |")
        total_idx += 1
