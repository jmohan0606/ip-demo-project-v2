#!/usr/bin/env python3
"""Bounded sample-data expansion (CLAUDE.md Section 9.3, PHASE 2 guardrails in 9.11).

WHAT THIS DOES (deterministic, idempotent):

A. RELABEL display names in place — same ids, same row counts, same numeric values:
   divisions (3), regions (6), markets (12), branches (24, real city/state),
   households (360), accounts (720), product subcategories (16), products (64),
   CRM opportunity names (180), CRM activity subject/notes/next_action (300),
   coaching session summaries + action-item texts (72, item COUNTS preserved).

B. EXTEND history by exactly 12 OLDER months (2023-08 .. 2024-07 -> 36 periods).
   All additions predate the anchored LTM window (2025-06-01..2026-06-30 for
   as_of 2026-07-03), so every verified figure (A001 revenue_ltm 387,293.22,
   A020 539,262.90, etc.) is untouched by construction — and verified by rerun.
   Adds: 12 time_period rows, 720 monthly_aum/ncf/nnm rows each, 2,160
   monthly_product_revenue rows, ~5,040 revenue transactions, plus all edges.

C. NEW SCHEMA SEED for phx_dm_coaching_task (90 tasks) + 2 edges — backing data
   for the Section 9.5 "manager assigns coaching task" feature.

D. Update manifest: 3 new entries (orders 183-185) + expected_rows for every
   appended file. Never rewrites untouched rows — appends and single-column
   relabels only.

GUARDRAILS honored:
 - No mutation of any numeric/status/date column on existing rows.
 - Idempotent: reruns detect the PER202308 period / renamed divisions / task
   file and skip the corresponding step.
"""
from __future__ import annotations

import csv
import json
import random
import zlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "data/sample/vertices"
E = ROOT / "data/sample/edges"
MANIFEST = ROOT / "data/manifest.json"

OLD_MONTHS = [(2023, m) for m in range(8, 13)] + [(2024, m) for m in range(1, 8)]

changed_files: set[str] = set()


def rng_for(*key) -> random.Random:
    return random.Random(zlib.crc32(":".join(str(k) for k in key).encode()))


def read(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def write(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    changed_files.add(str(path.relative_to(ROOT / "data/sample")))


def append(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writerows(rows)
    changed_files.add(str(path.relative_to(ROOT / "data/sample")))


def month_end(y: int, m: int) -> str:
    days = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return f"{y:04d}-{m:02d}-{days:02d}"


# --------------------------------------------------------------------------
# A. Real-world display names (relabel in place)
# --------------------------------------------------------------------------

DIVISIONS = {"D01": ("Eastern Division", "EAST"), "D02": ("Central Division", "CENT"),
             "D03": ("Western Division", "WEST")}

REGION_POOL = {  # per division, in region-id order
    "D01": [("Northeast Region", "NER"), ("Southeast Region", "SER")],
    "D02": [("Great Lakes Region", "GLR"), ("South Central Region", "SCR")],
    "D03": [("Mountain West Region", "MWR"), ("Pacific Region", "PAC")],
}

MARKET_POOL = {  # per region name, in market-id order
    "Northeast Region": [("Boston Metro", "BOS"), ("New York Metro", "NYC")],
    "Southeast Region": [("Atlanta Metro", "ATL"), ("South Florida", "SFL")],
    "Great Lakes Region": [("Chicago Metro", "CHI"), ("Detroit Metro", "DET")],
    "South Central Region": [("Dallas-Fort Worth", "DFW"), ("Houston Metro", "HOU")],
    "Mountain West Region": [("Denver Metro", "DEN"), ("Phoenix Metro", "PHX")],
    "Pacific Region": [("San Francisco Bay Area", "SFB"), ("Los Angeles Metro", "LAX")],
}

BRANCH_POOL = {  # per market name, in branch-id order
    "Boston Metro": [("Back Bay Office", "Boston", "MA"), ("Financial District Office", "Boston", "MA")],
    "New York Metro": [("Midtown Manhattan Office", "New York", "NY"), ("Long Island Office", "Garden City", "NY")],
    "Atlanta Metro": [("Buckhead Office", "Atlanta", "GA"), ("Alpharetta Office", "Alpharetta", "GA")],
    "South Florida": [("Brickell Office", "Miami", "FL"), ("Palm Beach Office", "West Palm Beach", "FL")],
    "Chicago Metro": [("The Loop Office", "Chicago", "IL"), ("Naperville Office", "Naperville", "IL")],
    "Detroit Metro": [("Birmingham Office", "Birmingham", "MI"), ("Ann Arbor Office", "Ann Arbor", "MI")],
    "Dallas-Fort Worth": [("Uptown Dallas Office", "Dallas", "TX"), ("Fort Worth Office", "Fort Worth", "TX")],
    "Houston Metro": [("Galleria Office", "Houston", "TX"), ("The Woodlands Office", "The Woodlands", "TX")],
    "Denver Metro": [("Cherry Creek Office", "Denver", "CO"), ("Boulder Office", "Boulder", "CO")],
    "Phoenix Metro": [("Camelback Office", "Phoenix", "AZ"), ("Scottsdale Office", "Scottsdale", "AZ")],
    "San Francisco Bay Area": [("Embarcadero Office", "San Francisco", "CA"), ("Palo Alto Office", "Palo Alto", "CA")],
    "Los Angeles Metro": [("Century City Office", "Los Angeles", "CA"), ("Newport Beach Office", "Newport Beach", "CA")],
}

SURNAMES = [
    "Whitfield", "Calloway", "Sinclair", "Pemberton", "Ashworth", "Lockhart", "Fairbanks", "Winslow",
    "Hargrove", "Ellsworth", "Mercer", "Thornton", "Caldwell", "Prescott", "Vandenberg", "Ridgeway",
    "Montgomery", "Blackwood", "Sterling", "Kensington", "Abernathy", "Beaumont", "Carrington", "Delacroix",
    "Everhart", "Fitzgerald", "Galloway", "Harrington", "Ingram", "Jennings", "Kirkland", "Langford",
    "Marchetti", "Northrup", "Oakes", "Pennington", "Quimby", "Rothschild", "Saunders", "Templeton",
    "Underwood", "Vaughn", "Wexler", "Yates", "Zimmerman", "Alcott", "Bradshaw", "Chamberlain",
    "Donnelly", "Eastman", "Falkner", "Granger", "Holloway", "Irving", "Jamison", "Keating",
    "Lancaster", "Middleton", "Nakamura", "Ortega", "Pruitt", "Quinn", "Radcliffe", "Stanhope",
    "Tanaka", "Urbina", "Villanueva", "Weatherford", "Xu", "Youngblood", "Ziegler", "Armitage",
    "Boswell", "Cavanaugh", "Drummond", "Eckhart", "Farnsworth", "Goldstein", "Hutchinson", "Iverson",
    "Jefferson", "Kowalski", "Lindqvist", "MacAllister", "Novak", "O'Donnell", "Petrov", "Quintero",
    "Rosenberg", "Sandoval", "Takahashi", "Ulrich", "Vance", "Whitmore", "Xiong", "Yamamoto",
    "Zhao", "Ainsley", "Barrington", "Crawford", "Devereaux", "Emerson", "Foster", "Gallagher",
    "Hawthorne", "Ibrahim", "Josephson", "Kaplan", "Livingston", "Moreau", "Nystrom", "Okafor",
    "Palmer", "Quigley", "Remington", "Silverstein", "Thibodeaux", "Umana", "Vasquez", "Wilkerson",
]

FIRST_NAMES = ["James", "Eleanor", "Michael", "Margaret", "Robert", "Catherine", "David", "Susan",
               "Thomas", "Patricia", "Daniel", "Laura", "Steven", "Rebecca", "Paul", "Diane",
               "Andrew", "Karen", "Charles", "Nancy", "Gregory", "Helen", "Marcus", "Julia"]

SUBCATEGORIES = {  # keyed by category name, in subcategory-id order
    "Managed Accounts": ["Separately Managed Accounts", "Unified Managed Accounts"],
    "Brokerage": ["Full-Service Brokerage", "Directed Brokerage"],
    "Fixed Income": ["Municipal Bonds", "Corporate & Treasury Bonds"],
    "Equities": ["US Equities", "International Equities"],
    "Mutual Funds": ["Equity Funds", "Balanced & Income Funds"],
    "Alternatives": ["Private Markets", "Hedge Strategies"],
    "Cash & Lending": ["Cash Management", "Securities-Based Lending"],
    "Insurance": ["Annuities", "Life Insurance"],
}

PRODUCTS = {  # 4 real-sounding products per subcategory name, in product-id order
    "Separately Managed Accounts": ["Northstar SMA Core Equity", "Northstar SMA Dividend Growth",
                                    "Northstar SMA Tax-Managed Value", "Northstar SMA Small Cap Select"],
    "Unified Managed Accounts": ["Northstar UMA Balanced Portfolio", "Northstar UMA Growth Portfolio",
                                 "Northstar UMA Income Portfolio", "Northstar UMA ESG Portfolio"],
    "Full-Service Brokerage": ["Premier Brokerage Account", "Select Brokerage Account",
                               "Active Trader Brokerage", "Retirement Brokerage Account"],
    "Directed Brokerage": ["Advisor-Directed Portfolio", "Client-Directed Portfolio",
                           "Institutional Directed Account", "Legacy Directed Account"],
    "Municipal Bonds": ["National Muni Bond Ladder", "State-Preference Muni Portfolio",
                        "High-Grade Muni Income", "Short-Duration Muni Fund"],
    "Corporate & Treasury Bonds": ["Investment-Grade Corporate Ladder", "US Treasury Ladder",
                                   "Corporate Income Portfolio", "Inflation-Protected Bond Strategy"],
    "US Equities": ["US Large Cap Core", "US Mid Cap Growth", "US Small Cap Value", "US Dividend Aristocrats"],
    "International Equities": ["Developed Markets Equity", "Emerging Markets Equity",
                               "Global ex-US Core", "International Dividend Strategy"],
    "Equity Funds": ["Northstar Growth Fund", "Northstar Value Fund",
                     "Northstar Index 500 Fund", "Northstar Technology Fund"],
    "Balanced & Income Funds": ["Northstar Balanced Fund", "Northstar Income Fund",
                                "Northstar Conservative Allocation", "Northstar Target Retirement Series"],
    "Private Markets": ["Private Equity Access Fund", "Private Credit Fund",
                        "Real Estate Opportunities Fund", "Infrastructure Partners Fund"],
    "Hedge Strategies": ["Multi-Strategy Hedge Portfolio", "Long/Short Equity Strategy",
                         "Global Macro Strategy", "Managed Futures Strategy"],
    "Cash Management": ["Premium Money Market", "Insured Cash Sweep",
                        "Treasury Cash Reserve", "Certificates of Deposit Program"],
    "Securities-Based Lending": ["Portfolio Line of Credit", "Express Credit Line",
                                 "Margin Lending Program", "Custom Liquidity Facility"],
    "Annuities": ["Fixed Index Annuity", "Variable Annuity with Income Rider",
                  "Immediate Income Annuity", "Deferred Income Annuity"],
    "Life Insurance": ["Whole Life Policy", "Universal Life Policy",
                       "Variable Universal Life", "Term Life Conversion Program"],
}

ACCOUNT_TYPE_LABEL = {"IRA": "Traditional IRA", "BROKERAGE": "Individual Brokerage",
                      "MANAGED": "Managed Portfolio", "TRUST": "Family Trust Account"}

OPP_THEMES = ["401(k) Rollover", "Managed Account Conversion", "Estate Plan Funding",
              "Concentrated Stock Diversification", "529 Education Funding", "Retirement Income Plan",
              "Charitable Giving Strategy", "Insurance Coverage Review", "Securities-Based Line of Credit",
              "Alternative Investments Allocation", "Roth Conversion Strategy", "Business Sale Proceeds"]

ACTIVITY_SUBJECTS = {
    "MEETING": ["Quarterly Portfolio Review", "Annual Financial Plan Review", "Retirement Planning Session",
                "Estate Planning Discussion", "New Account Onboarding Meeting"],
    "CALL": ["Market Volatility Check-In", "RMD Planning Call", "Tax-Loss Harvesting Discussion",
             "Proposal Follow-Up Call", "Cash Needs Discussion"],
    "EMAIL": ["Quarterly Performance Summary Sent", "Proposal Documents Sent", "Tax Documents Delivered",
              "Market Commentary Shared", "Meeting Recap & Next Steps"],
    "FOLLOW_UP": ["Post-Review Action Items", "Rollover Paperwork Follow-Up", "Beneficiary Update Follow-Up",
                  "Funding Confirmation Follow-Up", "Referral Introduction Follow-Up"],
    "REVIEW": ["Annual Suitability Review", "Portfolio Risk Alignment Review", "Fee & Service Review",
               "Concentration Risk Review", "Financial Plan Progress Review"],
}

ACTIVITY_NOTES = {
    "MEETING": "Met with the household to walk through {topic_lc}. Reviewed allocation versus plan targets and agreed on next steps.",
    "CALL": "Spoke with the client regarding {topic_lc}. Addressed outstanding questions and confirmed follow-up items.",
    "EMAIL": "Delivered materials for {topic_lc}. Flagged key figures and invited questions before the next review.",
    "FOLLOW_UP": "Followed up on {topic_lc}. Confirmed remaining paperwork and owners for each open item.",
    "REVIEW": "Completed {topic_lc}. Documented findings and updated the client file with current risk and objectives.",
}

NEXT_ACTIONS = ["Send meeting recap", "Schedule follow-up call", "Prepare updated proposal",
                "Update financial plan", "Send requested documents", "Book next review"]

COACHING_SUMMARIES = [
    "Reviewed pipeline health and prioritized the two largest open opportunities; agreed on weekly follow-up cadence.",
    "Walked through AGP milestone attainment; identified referral conversion as the key gap and set a 30-day target.",
    "Coached on managed-account positioning for top households; role-played the upgrade conversation.",
    "Reviewed overdue lead follow-ups; cleared blockers and committed to same-week first-touch on new leads.",
    "Discussed client engagement cadence for at-risk households; scheduled proactive outreach for the top five.",
    "Analyzed revenue mix versus peers; built an action list to deepen fixed-income penetration.",
    "Reviewed KPI trends against milestone targets; flagged NNM pacing and agreed on a prospecting push.",
    "Session focused on referral sourcing from CPA partners; drafted an introduction plan for two centers of influence.",
]

ACTION_ITEM_POOL = [
    "Call top three open opportunities this week", "Complete overdue lead follow-ups",
    "Book annual reviews for five at-risk households", "Draft managed-account upgrade proposals",
    "Ask two satisfied clients for referrals", "Update pipeline stages in CRM",
    "Prepare NNM pacing plan for next milestone", "Schedule CPA partner introduction",
]


def relabel() -> None:
    hdr, divs = read(V / "phx_dm_division.csv")
    if divs and divs[0]["division_name"] != "Division 1":
        print("A. relabel: already applied, skipping")
        return

    # divisions
    for r in divs:
        name, code = DIVISIONS[r["division_id"]]
        r["division_name"], r["division_code"] = name, code
    write(V / "phx_dm_division.csv", hdr, divs)

    # regions (assign per parent division, in id order)
    _, rd = read(E / "phx_dm_region_in_division.csv")
    region_parent = {r["from_id"]: r["to_id"] for r in rd}
    used = defaultdict(int)
    hdr, regions = read(V / "phx_dm_region.csv")
    region_name = {}
    for r in sorted(regions, key=lambda x: x["region_id"]):
        div = region_parent[r["region_id"]]
        name, code = REGION_POOL[div][used[div]]
        used[div] += 1
        r["region_name"], r["region_code"] = name, code
        region_name[r["region_id"]] = name
    write(V / "phx_dm_region.csv", hdr, regions)

    # markets
    _, mr = read(E / "phx_dm_market_in_region.csv")
    market_parent = {r["from_id"]: r["to_id"] for r in mr}
    used = defaultdict(int)
    hdr, markets = read(V / "phx_dm_market.csv")
    market_name = {}
    for r in sorted(markets, key=lambda x: x["market_id"]):
        reg = region_name[market_parent[r["market_id"]]]
        name, code = MARKET_POOL[reg][used[reg]]
        used[reg] += 1
        r["market_name"], r["market_code"] = name, code
        market_name[r["market_id"]] = name
    write(V / "phx_dm_market.csv", hdr, markets)

    # branches (name + real city/state)
    _, bm = read(E / "phx_dm_branch_in_market.csv")
    branch_parent = {r["from_id"]: r["to_id"] for r in bm}
    used = defaultdict(int)
    hdr, branches = read(V / "phx_dm_branch.csv")
    for r in sorted(branches, key=lambda x: x["branch_id"]):
        mkt = market_name[branch_parent[r["branch_id"]]]
        name, city, state = BRANCH_POOL[mkt][used[mkt]]
        used[mkt] += 1
        r["branch_name"], r["city"], r["state"] = name, city, state
        r["branch_code"] = f"{MARKET_POOL_CODE[mkt]}{used[mkt]}"
    write(V / "phx_dm_branch.csv", hdr, branches)

    # households
    hdr, households = read(V / "phx_dm_household.csv")
    hh_surname = {}
    for i, r in enumerate(sorted(households, key=lambda x: x["household_id"])):
        surname = SURNAMES[i % len(SURNAMES)]
        pattern = i // len(SURNAMES)
        if pattern == 0:
            name = f"The {surname} Family"
        elif pattern == 1:
            name = f"{surname} Family Trust"
        else:
            g = rng_for("hh", r["household_id"])
            a, b = g.sample(FIRST_NAMES, 2)
            name = f"{a} & {b} {surname}"
        r["household_name"] = name
        hh_surname[r["household_id"]] = surname
    write(V / "phx_dm_household.csv", hdr, households)

    # accounts — "<Surname> <Type Label>", suffixed if the household repeats a type
    _, hoa = read(E / "phx_dm_household_owns_account.csv")
    acct_hh = {r["to_id"]: r["from_id"] for r in hoa}
    hdr, accounts = read(V / "phx_dm_account.csv")
    seen: dict[tuple, int] = defaultdict(int)
    for r in sorted(accounts, key=lambda x: x["account_id"]):
        hh = acct_hh.get(r["account_id"])
        surname = hh_surname.get(hh, "Client")
        label = ACCOUNT_TYPE_LABEL.get(r["account_type"], r["account_type"].title())
        seen[(hh, label)] += 1
        n = seen[(hh, label)]
        r["account_name"] = f"{surname} {label}" + (f" {['','II','III','IV','V'][n-1]}" if n > 1 else "")
    write(V / "phx_dm_account.csv", hdr, accounts)

    # subcategories + products
    _, sc = read(E / "phx_dm_subcategory_in_category.csv")
    sub_parent = {r["from_id"]: r["to_id"] for r in sc}
    _, cats = read(V / "phx_dm_product_category.csv")
    cat_name = {r["category_id"]: r["category_name"] for r in cats}
    used = defaultdict(int)
    hdr, subs = read(V / "phx_dm_product_subcategory.csv")
    sub_name = {}
    for r in sorted(subs, key=lambda x: x["subcategory_id"]):
        cn = cat_name[sub_parent[r["subcategory_id"]]]
        r["subcategory_name"] = SUBCATEGORIES[cn][used[cn]]
        used[cn] += 1
        sub_name[r["subcategory_id"]] = r["subcategory_name"]
    write(V / "phx_dm_product_subcategory.csv", hdr, subs)

    _, ps = read(E / "phx_dm_product_in_subcategory.csv")
    prod_parent = {r["from_id"]: r["to_id"] for r in ps}
    used = defaultdict(int)
    hdr, prods = read(V / "phx_dm_product.csv")
    for r in sorted(prods, key=lambda x: x["product_id"]):
        sn = sub_name[prod_parent[r["product_id"]]]
        r["product_name"] = PRODUCTS[sn][used[sn]]
        used[sn] += 1
    write(V / "phx_dm_product.csv", hdr, prods)

    # household display names for CRM opportunity titles
    hh_display = {r["household_id"]: r["household_name"] for r in households}
    _, oh = read(E / "phx_dm_crm_opportunity_for_household.csv")
    opp_hh = {r["from_id"]: r["to_id"] for r in oh}
    hdr, opps = read(V / "phx_dm_crm_opportunity.csv")
    for r in opps:
        g = rng_for("opp", r["crm_opportunity_id"])
        theme = g.choice(OPP_THEMES)
        hh = hh_display.get(opp_hh.get(r["crm_opportunity_id"], ""), "Prospect Household")
        r["name"] = f"{theme} — {hh}"
    write(V / "phx_dm_crm_opportunity.csv", hdr, opps)

    # CRM activities — varied subject/notes/next_action per type (text only)
    hdr, acts = read(V / "phx_dm_crm_activity.csv")
    for r in acts:
        g = rng_for("act", r["activity_id"])
        pool = ACTIVITY_SUBJECTS.get(r["activity_type"], ACTIVITY_SUBJECTS["MEETING"])
        subject = g.choice(pool)
        r["subject"] = subject
        note_tpl = ACTIVITY_NOTES.get(r["activity_type"], ACTIVITY_NOTES["MEETING"])
        r["notes_summary"] = note_tpl.format(topic_lc=subject[0].lower() + subject[1:])
        r["next_action"] = g.choice(NEXT_ACTIONS)
    write(V / "phx_dm_crm_activity.csv", hdr, acts)

    # coaching sessions — varied summary, action-item COUNT preserved per row
    hdr, sessions = read(V / "phx_dm_coaching_session.csv")
    for r in sessions:
        g = rng_for("coach", r["session_id"])
        r["summary"] = g.choice(COACHING_SUMMARIES)
        try:
            n = len(json.loads(r["action_items_json"] or "[]"))
        except Exception:
            n = 2
        r["action_items_json"] = json.dumps(g.sample(ACTION_ITEM_POOL, min(n, len(ACTION_ITEM_POOL))))
    write(V / "phx_dm_coaching_session.csv", hdr, sessions)
    print("A. relabel: applied")


MARKET_POOL_CODE = {name: code for pools in MARKET_POOL.values() for name, code in pools}


# --------------------------------------------------------------------------
# B. 12 older months of history (2023-08 .. 2024-07)
# --------------------------------------------------------------------------

def extend_history() -> None:
    hdr_tp, periods = read(V / "phx_dm_time_period.csv")
    if any(p["period_id"] == "PER202308" for p in periods):
        print("B. history: already applied, skipping")
        return

    # 1. time periods
    new_periods = []
    for y, m in OLD_MONTHS:
        label = f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]} {y}"
        new_periods.append({
            "period_id": f"PER{y:04d}{m:02d}", "period_type": "MONTH",
            "start_date": f"{y:04d}-{m:02d}-01", "end_date": month_end(y, m),
            "year": y, "quarter": (m - 1) // 3 + 1, "month": m, "label": label,
        })
    # keep chronological order: new (older) months first
    write(V / "phx_dm_time_period.csv", hdr_tp, new_periods + periods)

    # advisor context: served households, household accounts, monthly product triple
    _, ash = read(E / "phx_dm_advisor_serves_household.csv")
    adv_households = defaultdict(list)
    for r in ash:
        adv_households[r["from_id"]].append(r["to_id"])
    _, hoa = read(E / "phx_dm_household_owns_account.csv")
    hh_accounts = defaultdict(list)
    for r in hoa:
        hh_accounts[r["from_id"]].append(r["to_id"])
    _, prfa = read(E / "phx_dm_product_revenue_for_advisor.csv")
    _, prfp = read(E / "phx_dm_product_revenue_for_product.csv")
    pr_product = {r["from_id"]: r["to_id"] for r in prfp}
    adv_products = defaultdict(list)  # advisor -> the 3 products of their PER202408 revenue rows
    for r in prfa:
        if "_PER202408_" in r["from_id"]:
            adv_products[r["to_id"]].append(pr_product[r["from_id"]])

    # anchor levels from existing data
    hdr_tx, txs = read(V / "phx_dm_revenue_transaction.csv")
    _, tfa = read(E / "phx_dm_transaction_for_advisor.csv")
    tx_advisor = {r["from_id"]: r["to_id"] for r in tfa}
    monthly_rev = defaultdict(float)  # (advisor, yyyy-mm) -> revenue
    type_pool = defaultdict(list)
    for r in txs:
        adv = tx_advisor.get(r["transaction_id"])
        if adv is None:
            continue
        ym = r["transaction_date"][:7]
        monthly_rev[(adv, ym)] += float(r["revenue_amount"] or 0)
        if len(type_pool[adv]) < 40:
            type_pool[adv].append(r["transaction_type"])
    advisors = sorted(adv_households)
    base_level = {a: sum(monthly_rev[(a, f"2024-{m:02d}")] for m in (8, 9, 10, 11, 12)) / 5 for a in advisors}

    hdr_aum, aums = read(V / "phx_dm_monthly_aum.csv")
    aum_2024_08 = {}
    for r in aums:
        if r["aum_id"].endswith("_PER202408"):
            aum_2024_08[r["aum_id"].split("_")[1]] = float(r["aum_amount"])
    hdr_ncf, ncfs = read(V / "phx_dm_monthly_ncf.csv")
    hdr_nnm, nnms = read(V / "phx_dm_monthly_nnm.csv")
    ncf_pool = defaultdict(list)
    for r in ncfs:
        ncf_pool[r["ncf_id"].split("_")[1]].append(float(r["ncf_amount"]))
    nnm_pool = defaultdict(list)
    for r in nnms:
        nnm_pool[r["nnm_id"].split("_")[1]].append(float(r["nnm_amount"]))

    seasonal = {1: 1.04, 2: 0.96, 3: 1.02, 4: 1.05, 5: 0.98, 6: 1.0,
                7: 0.94, 8: 0.95, 9: 1.01, 10: 1.03, 11: 0.99, 12: 1.08}

    next_tx = max(int(t["transaction_id"][2:]) for t in txs) + 1

    new_tx, e_tfa, e_tfh, e_tfacct, e_tfp, e_tip = [], [], [], [], [], []
    new_pr, e_prfa, e_prfp, e_prip = [], [], [], []
    new_aum, e_aumfa, e_aumip = [], [], []
    new_ncf, e_ncffa, e_ncfip = [], [], []
    new_nnm, e_nnmfa, e_nnmip = [], [], []

    for adv in advisors:
        products = adv_products[adv][:3] or ["P001", "P002", "P003"]
        households = adv_households[adv]
        # AUM back-cast from 2024-08, walking backwards
        aum_next = aum_2024_08.get(adv, 10_000_000.0)
        aum_series = {}
        for y, m in reversed(OLD_MONTHS):  # 2024-07 back to 2023-08
            g = rng_for("aum", adv, y, m)
            aum_next = round(aum_next * (1 - (0.003 + g.random() * 0.007)), 0)
            aum_series[(y, m)] = aum_next

        for idx, (y, m) in enumerate(OLD_MONTHS):
            g = rng_for("tx", adv, y, m)
            period = f"PER{y:04d}{m:02d}"
            # revenue: gently lower further back, seasonal shape, deterministic noise
            target = base_level[adv] * (0.80 + 0.015 * idx) * seasonal[m] * (1 + g.uniform(-0.06, 0.06))
            n = g.randint(5, 9)
            weights = [g.uniform(0.5, 1.5) for _ in range(n)]
            wsum = sum(weights)
            per_product_rev = defaultdict(float)
            for w in weights:
                tx_id = f"TX{next_tx:07d}"
                next_tx += 1
                amount = round(target * w / wsum, 2)
                day = g.randint(1, int(month_end(y, m)[8:10]))
                hh = g.choice(households)
                acct = g.choice(hh_accounts[hh]) if hh_accounts[hh] else None
                prod = g.choice(products)
                ttype = g.choice(type_pool[adv] or ["FEE"])
                gross = round(amount * g.uniform(15, 22), 2)
                new_tx.append({
                    "transaction_id": tx_id, "transaction_date": f"{y:04d}-{m:02d}-{day:02d}",
                    "revenue_amount": amount, "transaction_type": ttype,
                    "quantity": round(g.uniform(5, 60), 2), "gross_amount": gross,
                    "source_system": "IPERFORM",
                })
                e_tfa.append({"from_id": tx_id, "to_id": adv})
                e_tfh.append({"from_id": tx_id, "to_id": hh})
                if acct:
                    e_tfacct.append({"from_id": tx_id, "to_id": acct})
                e_tfp.append({"from_id": tx_id, "to_id": prod})
                e_tip.append({"from_id": tx_id, "to_id": period})
                per_product_rev[prod] += amount

            # monthly product revenue = per-product sums of the generated txs
            for i, prod in enumerate(products):
                pr_id = f"PR_{adv}_{period}_{i}"
                new_pr.append({"product_revenue_id": pr_id, "month_end": month_end(y, m),
                               "revenue_amount": round(per_product_rev.get(prod, 0.0), 2)})
                e_prfa.append({"from_id": pr_id, "to_id": adv})
                e_prfp.append({"from_id": pr_id, "to_id": prod})
                e_prip.append({"from_id": pr_id, "to_id": period})

            aum_id = f"AUM_{adv}_{period}"
            new_aum.append({"aum_id": aum_id, "month_end": month_end(y, m), "aum_amount": aum_series[(y, m)]})
            e_aumfa.append({"from_id": aum_id, "to_id": adv})
            e_aumip.append({"from_id": aum_id, "to_id": period})

            g2 = rng_for("flow", adv, y, m)
            ncf_id = f"NCF_{adv}_{period}"
            ncf_val = round(g2.choice(ncf_pool[adv] or [0.0]) * g2.uniform(0.8, 1.2) / 10) * 10
            new_ncf.append({"ncf_id": ncf_id, "month_end": month_end(y, m), "ncf_amount": ncf_val})
            e_ncffa.append({"from_id": ncf_id, "to_id": adv})
            e_ncfip.append({"from_id": ncf_id, "to_id": period})

            nnm_id = f"NNM_{adv}_{period}"
            nnm_val = round(g2.choice(nnm_pool[adv] or [0.0]) * g2.uniform(0.8, 1.2) / 10) * 10
            new_nnm.append({"nnm_id": nnm_id, "month_end": month_end(y, m), "nnm_amount": nnm_val})
            e_nnmfa.append({"from_id": nnm_id, "to_id": adv})
            e_nnmip.append({"from_id": nnm_id, "to_id": period})

    edge_hdr = ["from_id", "to_id"]
    append(V / "phx_dm_revenue_transaction.csv", hdr_tx, new_tx)
    append(E / "phx_dm_transaction_for_advisor.csv", edge_hdr, e_tfa)
    append(E / "phx_dm_transaction_for_household.csv", edge_hdr, e_tfh)
    append(E / "phx_dm_transaction_for_account.csv", edge_hdr, e_tfacct)
    append(E / "phx_dm_transaction_for_product.csv", edge_hdr, e_tfp)
    append(E / "phx_dm_transaction_in_period.csv", edge_hdr, e_tip)
    append(V / "phx_dm_monthly_product_revenue.csv", ["product_revenue_id", "month_end", "revenue_amount"], new_pr)
    append(E / "phx_dm_product_revenue_for_advisor.csv", edge_hdr, e_prfa)
    append(E / "phx_dm_product_revenue_for_product.csv", edge_hdr, e_prfp)
    append(E / "phx_dm_product_revenue_in_period.csv", edge_hdr, e_prip)
    append(V / "phx_dm_monthly_aum.csv", hdr_aum, new_aum)
    append(E / "phx_dm_aum_for_advisor.csv", edge_hdr, e_aumfa)
    append(E / "phx_dm_aum_in_period.csv", edge_hdr, e_aumip)
    append(V / "phx_dm_monthly_ncf.csv", hdr_ncf, new_ncf)
    append(E / "phx_dm_ncf_for_advisor.csv", edge_hdr, e_ncffa)
    append(E / "phx_dm_ncf_in_period.csv", edge_hdr, e_ncfip)
    append(V / "phx_dm_monthly_nnm.csv", hdr_nnm, new_nnm)
    append(E / "phx_dm_nnm_for_advisor.csv", edge_hdr, e_nnmfa)
    append(E / "phx_dm_nnm_in_period.csv", edge_hdr, e_nnmip)
    print(f"B. history: +{len(new_periods)} periods, +{len(new_tx)} transactions, "
          f"+{len(new_pr)} product-revenue rows, +{len(new_aum)}/{len(new_ncf)}/{len(new_nnm)} aum/ncf/nnm rows")


# --------------------------------------------------------------------------
# C. Coaching task seed (new vertex type phx_dm_coaching_task)
# --------------------------------------------------------------------------

TASK_TEMPLATES = [
    ("Complete overdue lead follow-ups", "CRM_EXECUTION",
     "Work the overdue lead queue to zero this week and log next actions in CRM."),
    ("Advance top pipeline opportunity", "PIPELINE",
     "Move the largest open opportunity to the next stage; document the client's decision criteria."),
    ("Book annual reviews for at-risk households", "CLIENT_ENGAGEMENT",
     "Schedule annual reviews with the five households showing the longest gap since last activity."),
    ("Close the AGP milestone execution gap", "AGP_MILESTONE",
     "Focus on the KPIs behind the current milestone; bring attainment above target before the due date."),
    ("Present managed-account upgrade to top clients", "MANAGED_MIX",
     "Prepare and deliver managed-account proposals for the three largest brokerage-heavy households."),
    ("Ask two clients for referrals", "CRM_EXECUTION",
     "Identify two highly satisfied clients from recent reviews and make a direct referral ask."),
    ("Build NNM pacing plan", "AGP_MILESTONE",
     "Draft a month-by-month net-new-money plan to close the pacing gap to the next milestone."),
    ("Re-engage stalled referrals", "PIPELINE",
     "Contact every referral with no touch in 30+ days and set a concrete next step for each."),
]


def seed_coaching_tasks() -> None:
    task_file = V / "phx_dm_coaching_task.csv"
    if task_file.exists():
        print("C. coaching tasks: already applied, skipping")
        return
    _, mm = read(E / "phx_dm_mdw_manages_advisor.csv")
    manager_of = {r["to_id"]: r["from_id"] for r in mm}
    _, advisors = read(V / "phx_dm_advisor.csv")
    adv_ids = sorted(a["advisor_id"] for a in advisors)

    tasks, e_for, e_by = [], [], []
    n = 0
    statuses = ["OPEN", "IN_PROGRESS", "COMPLETED"]
    for i, adv in enumerate(adv_ids):
        count = 2 if i < 30 else 1
        for k in range(count):
            n += 1
            task_id = f"CTASK{n:04d}"
            g = rng_for("ctask", task_id)
            title, category, instruction = TASK_TEMPLATES[(i + k) % len(TASK_TEMPLATES)]
            status = statuses[(i + k) % 3]
            created = f"2026-{g.choice(['05','06'])}-{g.randint(1, 28):02d}"
            due = f"2026-07-{g.randint(10, 28):02d}"
            completed = f"2026-06-{g.randint(15, 30):02d}" if status == "COMPLETED" else ""
            manager = manager_of.get(adv, "U_MDW01")
            tasks.append({
                "task_id": task_id, "title": title, "category": category,
                "instruction": instruction, "status": status,
                "priority": g.choice(["HIGH", "MEDIUM", "MEDIUM", "LOW"]),
                "created_date": created, "due_date": due, "completed_date": completed,
                "created_by_user_id": manager,
            })
            e_for.append({"from_id": task_id, "to_id": adv})
            e_by.append({"from_id": task_id, "to_id": manager})

    write(task_file, ["task_id", "title", "category", "instruction", "status", "priority",
                      "created_date", "due_date", "completed_date", "created_by_user_id"], tasks)
    write(E / "phx_dm_coaching_task_for_advisor.csv", ["from_id", "to_id"], e_for)
    write(E / "phx_dm_coaching_task_assigned_by.csv", ["from_id", "to_id"], e_by)
    print(f"C. coaching tasks: +{len(tasks)} tasks, +{len(e_for)}+{len(e_by)} edges")


# --------------------------------------------------------------------------
# D. Manifest: new entries + expected_rows reconciliation
# --------------------------------------------------------------------------

NEW_MANIFEST_ENTRIES = [
    {
        "order": 183, "kind": "vertex", "file": "vertices/phx_dm_coaching_task.csv",
        "target": "phx_dm_coaching_task", "id_column": "task_id",
        "columns": {c: c for c in ["task_id", "title", "category", "instruction", "status", "priority",
                                   "created_date", "due_date", "completed_date", "created_by_user_id"]},
        "required_columns": ["task_id"], "dependencies": [], "expected_rows": 90,
    },
    {
        "order": 184, "kind": "edge", "file": "edges/phx_dm_coaching_task_for_advisor.csv",
        "target": "phx_dm_coaching_task_for_advisor",
        "from_type": "phx_dm_coaching_task", "to_type": "phx_dm_advisor",
        "from_column": "from_id", "to_column": "to_id",
        "columns": {"from_id": "from_id", "to_id": "to_id"},
        "required_columns": ["from_id", "to_id"],
        "dependencies": ["vertices/phx_dm_coaching_task.csv", "vertices/phx_dm_advisor.csv"],
        "expected_rows": 90,
    },
    {
        "order": 185, "kind": "edge", "file": "edges/phx_dm_coaching_task_assigned_by.csv",
        "target": "phx_dm_coaching_task_assigned_by",
        "from_type": "phx_dm_coaching_task", "to_type": "phx_dm_persona_user",
        "from_column": "from_id", "to_column": "to_id",
        "columns": {"from_id": "from_id", "to_id": "to_id"},
        "required_columns": ["from_id", "to_id"],
        "dependencies": ["vertices/phx_dm_coaching_task.csv", "vertices/phx_dm_persona_user.csv"],
        "expected_rows": 90,
    },
]


def update_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = manifest["files"]
    have = {e["file"] for e in files}
    for entry in NEW_MANIFEST_ENTRIES:
        if entry["file"] not in have:
            files.append(entry)
    # reconcile expected_rows with actual for every entry (only appended files change)
    fixed = 0
    for e in files:
        path = ROOT / "data/sample" / e["file"]
        with path.open(newline="", encoding="utf-8-sig") as f:
            actual = sum(1 for _ in csv.DictReader(f))
        if e.get("expected_rows") != actual:
            e["expected_rows"] = actual
            fixed += 1
    manifest["version"] = "1.2"
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"D. manifest: {len(files)} entries, expected_rows reconciled on {fixed} files, version 1.2")


if __name__ == "__main__":
    relabel()
    extend_history()
    seed_coaching_tasks()
    update_manifest()
    print("Done. Changed files:", len(changed_files))
