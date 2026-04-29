#!/usr/bin/env python3
"""
Yourewild link checker
Reads sites.json and checks every URL field for broken links.
Usage:
  python3 link_checker.py                  # checks sites.json in current directory
  python3 link_checker.py path/to/sites.json
"""

import json
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Config ────────────────────────────────────────────────────
TIMEOUT      = 10      # seconds per request
MAX_WORKERS  = 10      # concurrent requests
USER_AGENT   = 'Yourewild-LinkChecker/1.0 (yourewild.co.uk)'

# URL fields to check per site
# Each entry is (field_path, label) where field_path supports dot notation
URL_FIELDS = [
    ('url',           'website'),
    ('yourewild.parking', 'parking'),
]

# ── Helpers ───────────────────────────────────────────────────
def get_nested(obj, path):
    """Get a value from a nested dict using dot notation."""
    keys = path.split('.')
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj

def check_url(url, label, site_name):
    """Check a single URL. Returns (site_name, label, url, status, ok)."""
    if not url:
        return (site_name, label, url, 'skipped', None)
    try:
        req = urllib.request.Request(
            url,
            method='HEAD',
            headers={'User-Agent': USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            code = resp.status
            ok   = 200 <= code < 400
            return (site_name, label, url, str(code), ok)
    except urllib.error.HTTPError as e:
        return (site_name, label, url, str(e.code), False)
    except urllib.error.URLError as e:
        reason = str(e.reason)
        return (site_name, label, url, f'URLError: {reason}', False)
    except Exception as e:
        return (site_name, label, url, f'Error: {e}', False)

def load_sites(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def build_tasks(sites):
    """Build list of (site_name, label, url) tuples to check."""
    tasks = []
    for site in sites:
        name = site.get('name', 'Unknown')
        for field_path, label in URL_FIELDS:
            url = get_nested(site, field_path)
            if url:
                tasks.append((name, label, url))
    return tasks

# ── Main ──────────────────────────────────────────────────────
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'sites.json'

    print(f"Yourewild Link Checker")
    print(f"Loading: {path}\n")

    try:
        sites = load_sites(path)
    except FileNotFoundError:
        print(f"Error: {path} not found. Run from the repo root or pass the path as an argument.")
        sys.exit(1)

    tasks = build_tasks(sites)
    total_sites  = len(sites)
    total_urls   = len(tasks)
    null_count   = sum(
        1 for site in sites
        for field_path, _ in URL_FIELDS
        if not get_nested(site, field_path)
    )

    print(f"Sites:      {total_sites}")
    print(f"URLs found: {total_urls}")
    print(f"Skipped (null): {null_count}\n")

    if total_urls == 0:
        print("No URLs to check. Fill in 'url' and 'parking' fields in sites.json first.")
        sys.exit(0)

    print(f"Checking {total_urls} URLs (timeout={TIMEOUT}s, workers={MAX_WORKERS})...\n")

    results  = []
    failures = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(check_url, url, label, name): (name, label, url)
            for name, label, url in tasks
        }
        done = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            done += 1
            site_name, label, url, status, ok = result
            if ok is False:
                symbol = '✗'
            elif ok is True:
                symbol = '✓'
            else:
                symbol = '–'
            print(f"  [{done:>3}/{total_urls}] {symbol}  {site_name} ({label}): {status}")

    # ── Summary ───────────────────────────────────────────────
    ok_results   = [r for r in results if r[4] is True]
    fail_results = [r for r in results if r[4] is False]
    skip_results = [r for r in results if r[4] is None]

    print(f"\n{'─'*60}")
    print(f"RESULTS")
    print(f"{'─'*60}")
    print(f"  OK:      {len(ok_results)}")
    print(f"  Failed:  {len(fail_results)}")
    print(f"  Skipped: {len(skip_results)}")

    if fail_results:
        print(f"\n{'─'*60}")
        print(f"BROKEN LINKS — fix these in sites.json")
        print(f"{'─'*60}")
        for site_name, label, url, status, _ in sorted(fail_results, key=lambda r: r[0]):
            print(f"  {site_name} ({label})")
            print(f"    URL:    {url}")
            print(f"    Status: {status}")
            print()
        sys.exit(1)  # non-zero exit so GitHub Actions marks the run as failed
    else:
        print(f"\nAll links OK.")
        sys.exit(0)

if __name__ == '__main__':
    main()
