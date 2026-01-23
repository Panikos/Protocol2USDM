#!/usr/bin/env python3
"""
Download final batch of trials to reach 30+ total.
"""

import os
import csv
import requests
import time
from pathlib import Path

OUTPUT_DIR = Path(r"C:\Users\panik\Documents\GitHub\Protcol2USDMv3\input\trial")
CT_API_BASE = "https://clinicaltrials.gov/api/v2/studies"
CT_DOC_BASE = "https://cdn.clinicaltrials.gov/large-docs"

TRIALS = [
    # Eli Lilly trials
    {"nct_id": "NCT03482102", "name": "SURPASS3", "sponsor": "Lilly", "condition": "T2DM"},
    {"nct_id": "NCT02460978", "name": "REWIND", "sponsor": "Lilly", "condition": "T2DM"},

    # BMS trials
    {"nct_id": "NCT02576509", "name": "CheckMate227", "sponsor": "BMS", "condition": "NSCLC"},
    {"nct_id": "NCT02041533", "name": "CheckMate025", "sponsor": "BMS", "condition": "RCC"},

    # Merck trials
    {"nct_id": "NCT02362594", "name": "KEYNOTE045", "sponsor": "Merck", "condition": "BladderCancer"},

    # More Janssen
    {"nct_id": "NCT03004833", "name": "TITAN", "sponsor": "Janssen", "condition": "ProstateCancer"},

    # Boehringer Ingelheim
    {"nct_id": "NCT02570672", "name": "EMPACROWN", "sponsor": "BI", "condition": "T2DM"},
]


def get_trial_details(nct_id):
    url = f"{CT_API_BASE}/{nct_id}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching {nct_id}: {e}")
    return None


def get_document_info(trial_data):
    docs = []
    try:
        doc_section = trial_data.get("documentSection", {})
        large_docs = doc_section.get("largeDocumentModule", {}).get("largeDocs", [])
        for doc in large_docs:
            docs.append({
                "label": doc.get("label", ""),
                "filename": doc.get("filename", ""),
            })
    except:
        pass
    return docs


def download_document(nct_id, filename, output_path):
    nct_suffix = nct_id[-2:]
    url = f"{CT_DOC_BASE}/{nct_suffix}/{nct_id}/{filename}"
    try:
        response = requests.get(url, timeout=120, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    except:
        pass
    return False


def extract_sites(trial_data):
    sites = []
    try:
        locations = trial_data.get("protocolSection", {}).get("contactsLocationsModule", {}).get("locations", [])
        for i, loc in enumerate(locations, 1):
            sites.append({
                "site_number": f"{i:03d}",
                "facility": loc.get("facility", "Research Site"),
                "city": loc.get("city", ""),
                "state": loc.get("state", ""),
                "country": loc.get("country", ""),
                "zip": loc.get("zip", ""),
                "status": loc.get("status", "Completed")
            })
    except:
        pass
    return sites


def create_sites_csv(sites, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Site Number", "Site Name", "Country", "City", "State", "Zip", "Status"])
        for site in sites:
            writer.writerow([site["site_number"], site["facility"], site["country"],
                           site["city"], site["state"], site["zip"], site["status"]])


def process_trial(trial_info):
    nct_id = trial_info["nct_id"]
    name = trial_info["name"]
    folder_name = f"{nct_id}_{name}"

    print(f"\nProcessing {folder_name}...")

    trial_dir = OUTPUT_DIR / folder_name
    trial_dir.mkdir(parents=True, exist_ok=True)

    trial_data = get_trial_details(nct_id)
    if not trial_data:
        return False

    docs = get_document_info(trial_data)
    protocol_downloaded = False
    sap_downloaded = False

    for doc in docs:
        label = doc["label"].lower()
        filename = doc["filename"]

        if "protocol" in label and "sap" in label:
            output_file = trial_dir / f"{folder_name}_Protocol_SAP.pdf"
            if download_document(nct_id, filename, output_file):
                print(f"  Downloaded Protocol+SAP")
                protocol_downloaded = sap_downloaded = True
        elif "protocol" in label and not protocol_downloaded:
            output_file = trial_dir / f"{folder_name}_Protocol.pdf"
            if download_document(nct_id, filename, output_file):
                print(f"  Downloaded Protocol")
                protocol_downloaded = True
        elif "statistical" in label or "sap" in label:
            output_file = trial_dir / f"{folder_name}_SAP.pdf"
            if download_document(nct_id, filename, output_file):
                print(f"  Downloaded SAP")
                sap_downloaded = True

    sites = extract_sites(trial_data)
    if sites:
        sites_file = trial_dir / f"{folder_name}_sites.csv"
        create_sites_csv(sites, sites_file)
        print(f"  Created sites file ({len(sites)} sites)")

    if protocol_downloaded and sap_downloaded:
        print(f"  SUCCESS")
        return True
    elif protocol_downloaded or sap_downloaded:
        print(f"  PARTIAL")
        return True
    return False


def main():
    print("Batch 3 - Final trials")
    for trial in TRIALS:
        try:
            process_trial(trial)
            time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
