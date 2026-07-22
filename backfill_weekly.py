#!/usr/bin/env python3
"""
One-off backfill script: creates weekly arxiv alert HTML files
for each week from June 20 to July 20, 2026.
Run this once, then delete it.
"""

import arxiv_alert_daily as alert
from datetime import date

# (override_date, days_to_search, label)
# override_date acts as "today" in the script:
#   yesterday = override_date - 1 day
#   start_window = yesterday - (days_to_search - 1)
weekly_runs = [
    # (date(2026, 6, 27), 8),   # covers Jun 20–26
    # (date(2026, 7,  4), 8),   # covers Jun 27–Jul 3
    (date(2026, 7, 11), 8),   # covers Jul 4–10
    (date(2026, 7, 18), 8),   # covers Jul 11–17
]

for run_date, days in weekly_runs:
    print(f"\n{'='*60}")
    print(f"Backfill run: override_date={run_date}, days={days}")
    print('='*60)

    # Temporarily override the date in the module
    # alert.OVERRIDE_DATE = run_date

    alert.arxiv_alert(
        'extragal/extragal_arxiv_' + str(run_date),
        days,
        start_date=run_date,
        categories=alert.categories_astroph,
        keywords=alert.keywords_extragal,
        excluded_categories=alert.excluded_astro_categories
    )
    alert.arxiv_alert(
        'agn/agn_arxiv_' + str(run_date),
        days,
        start_date=run_date,
        categories=alert.categories_astroph,
        keywords=alert.keywords_agn,
        excluded_categories=alert.excluded_astro_categories
    )
    alert.arxiv_alert(
        'ml/ml_arxiv_' + str(run_date),
        days,
        start_date=run_date,
        categories=alert.categories_ml,
        keywords=alert.keywords_ml
    )

# Reset override so the module is clean if imported again
alert.OVERRIDE_DATE = None
print("\nBackfill complete.")
