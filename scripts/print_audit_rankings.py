import json
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open("data/source_discovery_audit.json", encoding="utf-8") as f:
    data = json.load(f)

ranked = sorted(data, key=lambda x: x["pdf_count_sample"], reverse=True)

print("=" * 140)
print(" 📊 COMPLETE 34-CHANNEL SOURCE DISCOVERY AUDIT REPORT")
print("=" * 140)
print(f"{'#':<3} | {'USERNAME':<35} | {'ACC':<3} | {'HIST':<4} | {'LATEST MSG (DATE)':<23} | {'30D MSGS':<8} | {'PDFS/100':<8} | {'YIELD %':<7} | {'EST. YIELD':<16} | {'AUTH STATUS':<12} | {'REC BACKFILL':<12} | {'CATEGORY'}")
print("─" * 140)

for idx, c in enumerate(data, 1):
    latest_str = f"#{c['latest_msg_id']} ({c['latest_date']})" if c['latest_msg_id'] != 'N/A' else 'N/A'
    print(f"{idx:2d}. | {c['username']:<35} | {c['accessible']:<3} | {c['historical_access']:<4} | {latest_str:<23} | {c['msgs_last_30d']:<8} | {c['pdf_count_sample']:<8} | {c['pdf_yield_pct']:<7} | {c['estimated_pdf_yield']:<16} | {c['auth_status']:<12} | {c['recommended_backfill']:<12} | #{c['category']}")

print("─" * 140)
print("\n" + "=" * 140)
print(" 🏆 RANKING OF ALL 34 CHANNELS BY USEFUL PDF YIELD")
print("=" * 140)
for rank, c in enumerate(ranked, 1):
    latest_str = f"#{c['latest_msg_id']} ({c['latest_date']})" if c['latest_msg_id'] != 'N/A' else 'N/A'
    print(f"Rank {rank:2d}: {c['username']:<35} | {c['pdf_count_sample']:2d} PDFs / 100 msgs ({c['pdf_yield_pct']:4.1f}%) | Yield: {c['estimated_pdf_yield']:<18} | Rec: {c['recommended_backfill']:3d} msgs | #{c['category']:<12} | Title: {c['title']}")

print("=" * 140)
