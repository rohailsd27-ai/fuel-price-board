"""
Fuel price scraper for the South Asia Fuel Board.

What this does, in plain terms:
  1. Visits a couple of public price-tracking pages for each country.
  2. Pulls out the petrol and diesel price using pattern matching (regex).
  3. Fetches a fresh USD exchange rate for each currency.
  4. Writes everything into data.json, which the website reads.

If a source page can't be read or its numbers can't be found, this script
does NOT wipe out the old value — it keeps whatever was already in
data.json and marks that entry "stale" so the website can show a warning
instead of a wrong number. That's the main defence against a source
changing its page layout and silently breaking things.

This is meant to be run automatically by the GitHub Actions workflow in
.github/workflows/update-prices.yml, on a schedule. You can also run it
yourself locally with:  python scrape.py
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_FILE = Path(__file__).parent / "data.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FuelBoardBot/1.0)"}
TIMEOUT = 20

COUNTRIES = ["Pakistan", "India", "Bangladesh", "Afghanistan"]
FLAGS = {
    "Pakistan": "🇵🇰",
    "India": "🇮🇳",
    "Bangladesh": "🇧🇩",
    "Afghanistan": "🇦🇫",
}
CURRENCIES = {
    "Pakistan": "PKR",
    "India": "INR",
    "Bangladesh": "BDT",
    "Afghanistan": "AFN",
}


def log(msg):
    print(f"[scrape] {msg}", flush=True)


def fetch_text(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


# ---------------------------------------------------------------------------
# Primary source: globalpetrolprices.com — same table layout for every
# country, refreshed weekly, gives both local currency and a USD figure.
# ---------------------------------------------------------------------------
def scrape_globalpetrolprices(country):
    url = f"https://www.globalpetrolprices.com/{country}/"
    text = fetch_text(url)

    result = {}
    for fuel, label in (("petrol", "Gasoline prices"), ("diesel", "Diesel prices")):
        pattern = rf"{label}\s+(\d{{2}}\.\d{{2}}\.\d{{4}})\s+([\d,.]+)\s+([\d,.]+)"
        match = re.search(pattern, text)
        if match:
            date_str, local_price, usd_price = match.groups()
            result[fuel] = {
                "local": float(local_price.replace(",", "")),
                "usd": float(usd_price.replace(",", "")),
                "date": datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d"),
            }
    return result, url


# ---------------------------------------------------------------------------
# Secondary / faster source for Pakistan only. Pakistan has moved to a
# near-daily pricing mechanism, so the weekly aggregator above can lag by
# several days. This page is a standing "today's price" page (not a dated
# article), which tends to stay current.
# ---------------------------------------------------------------------------
def scrape_pakistan_pakwheels():
    url = "https://www.pakwheels.com/petroleum-prices-in-pakistan"
    text = fetch_text(url)
    pattern = (
        r"Petrol Price in Pakistan is Rs\.?\s*([\d,.]+)\s*/?\s*Ltr,?\s*"
        r"High Speed Diesel is Rs\.?\s*([\d,.]+)\s*/?\s*Ltr"
    )
    match = re.search(pattern, text)
    if not match:
        return None, url
    petrol, diesel = match.groups()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "petrol": {"local": float(petrol.replace(",", "")), "usd": None, "date": today},
        "diesel": {"local": float(diesel.replace(",", "")), "usd": None, "date": today},
    }, url


# ---------------------------------------------------------------------------
# Exchange rates: free, no API key required.
# ---------------------------------------------------------------------------
def fetch_exchange_rates():
    url = "https://open.er-api.com/v6/latest/USD"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("result") != "success":
        raise RuntimeError("exchange rate API did not return success")
    rates = payload["rates"]
    return {code: rates[code] for code in ("PKR", "INR", "BDT", "AFN") if code in rates}


def load_existing():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except json.JSONDecodeError:
            log("existing data.json is corrupt, starting fresh")
    return {"countries": {}, "rates": {}}


def merge_fuel(existing_fuel, scraped_fuel, source_label):
    """Keep the old value (marked stale) if scraping failed for this fuel."""
    if scraped_fuel:
        return {**scraped_fuel, "source": source_label, "stale": False}
    if existing_fuel:
        stale = dict(existing_fuel)
        stale["stale"] = True
        return stale
    return {"local": None, "usd": None, "date": None, "source": source_label, "stale": True}


def main():
    existing = load_existing()
    existing_countries = existing.get("countries", {})

    countries_out = {}
    any_failures = False

    for country in COUNTRIES:
        log(f"scraping {country}...")
        existing_entry = existing_countries.get(country, {})
        scraped = {}
        source_used = None

        if country == "Pakistan":
            try:
                pk_data, pk_url = scrape_pakistan_pakwheels()
                if pk_data:
                    scraped = pk_data
                    source_used = pk_url
            except Exception as exc:
                log(f"  pakwheels source failed for Pakistan: {exc}")

        # Fill in anything still missing (or every fuel, for non-Pakistan
        # countries) using the weekly aggregator.
        if "petrol" not in scraped or "diesel" not in scraped:
            try:
                gpp_data, gpp_url = scrape_globalpetrolprices(country)
                for fuel in ("petrol", "diesel"):
                    if fuel not in scraped and fuel in gpp_data:
                        scraped[fuel] = gpp_data[fuel]
                if source_used is None:
                    source_used = gpp_url
            except Exception as exc:
                log(f"  globalpetrolprices source failed for {country}: {exc}")
                any_failures = True

        countries_out[country] = {
            "name": country,
            "flag": FLAGS[country],
            "currency": CURRENCIES[country],
            "petrol": merge_fuel(existing_entry.get("petrol"), scraped.get("petrol"), source_used),
            "diesel": merge_fuel(existing_entry.get("diesel"), scraped.get("diesel"), source_used),
        }

    log("fetching exchange rates...")
    try:
        rates = fetch_exchange_rates()
    except Exception as exc:
        log(f"  exchange rate fetch failed: {exc}")
        rates = existing.get("rates", {})
        any_failures = True

    output = {
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "countries": countries_out,
        "rates": rates,
        "had_failures": any_failures,
    }

    DATA_FILE.write_text(json.dumps(output, indent=2))
    log(f"wrote {DATA_FILE}")

    if any_failures:
        log("completed with some failures (old values kept where needed)")
        sys.exit(0)  # don't fail the workflow — stale data is still shown


if __name__ == "__main__":
    main()
