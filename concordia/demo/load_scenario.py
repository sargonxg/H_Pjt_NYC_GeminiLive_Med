#!/usr/bin/env python3
"""
Load a CONCORDIA demo scenario via the REST API.

Usage:
    python demo/load_scenario.py demo/scenarios/hr_dispute.json
    python demo/load_scenario.py demo/scenarios/hr_dispute.json --base-url http://localhost:8080
"""

import argparse
import json
import sys
import time
import requests


def main():
    parser = argparse.ArgumentParser(description="Load a CONCORDIA demo scenario")
    parser.add_argument("scenario_file", help="Path to scenario JSON file")
    parser.add_argument("--base-url", default="http://localhost:8080",
                        help="CONCORDIA server base URL")
    args = parser.parse_args()

    # Load scenario
    with open(args.scenario_file) as f:
        scenario = json.load(f)

    base = args.base_url.rstrip("/")
    print(f"\n  CONCORDIA Scenario Loader")
    print(f"  {'='*40}")
    print(f"  Server: {base}")
    print(f"  Scenario: {scenario['title']}")
    print(f"  Parties: {len(scenario['parties'])}")
    print()

    # Check server
    try:
        r = requests.get(f"{base}/api/health", timeout=5)
        r.raise_for_status()
        health = r.json()
        print(f"  Server status: {health['status']}")
        print(f"  Gemini API: {health['gemini_api']}")
    except Exception as e:
        print(f"  ERROR: Cannot reach server at {base}")
        print(f"  Start it with: cd concordia/app && uvicorn main:app --port 8080")
        sys.exit(1)

    # Create case
    party_names = [p["name"] for p in scenario["parties"]]
    r = requests.post(f"{base}/api/cases", json={
        "title": scenario["title"],
        "parties": party_names,
    })
    r.raise_for_status()
    case_data = r.json()
    case_id = case_data["case_id"]
    print(f"\n  Case created: {case_id}")

    # Upload each party's story
    for i, party_info in enumerate(scenario["parties"]):
        api_party = case_data["parties"][i]
        party_id = api_party["party_id"]
        party_name = api_party["name"]

        print(f"\n  Uploading story for {party_name}...")

        # Upload main story
        r = requests.post(f"{base}/api/cases/{case_id}/upload", json={
            "party_id": party_id,
            "text": party_info["story"],
            "document_name": f"{party_name}'s Statement",
        })

        if r.ok:
            result = r.json()
            score = result.get("party_health", {}).get("score", "?")
            print(f"    Status: {result.get('status', 'unknown')}")
            print(f"    Party health: {score}%")
            print(f"    Format: {result.get('format_detected', 'unknown')}")
        else:
            print(f"    ERROR: {r.status_code} — {r.text[:200]}")

        # Upload any additional documents
        for j, doc in enumerate(party_info.get("documents", [])):
            if doc:
                r = requests.post(f"{base}/api/cases/{case_id}/upload", json={
                    "party_id": party_id,
                    "text": doc,
                    "document_name": f"Document {j+1}",
                })

        # Small delay between parties
        time.sleep(1)

    # Get final case state
    r = requests.get(f"{base}/api/cases/{case_id}")
    if r.ok:
        final = r.json()
        health = final.get("graph_health", {})
        print(f"\n  {'='*40}")
        print(f"  Case: {case_id}")
        print(f"  Phase: {final.get('phase', '?')}")
        print(f"  Graph health: {health.get('score', 0)}%")
        print(f"  Ready: {health.get('ready', False)}")
        if health.get("gaps"):
            print(f"  Gaps:")
            for gap in health["gaps"][:3]:
                print(f"    - {gap}")
        print(f"\n  Open: {base}")
        print()


if __name__ == "__main__":
    main()
