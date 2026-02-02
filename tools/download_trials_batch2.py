#!/usr/bin/env python3
"""
Download additional trials to replace the failed ones.
"""

import os
import json
import csv
import requests
import time
from pathlib import Path

OUTPUT_DIR = Path(r"C:\Users\panik\Documents\GitHub\Protcol2USDMv3\input\trial")
CT_API_BASE = "https://clinicaltrials.gov/api/v2/studies"
CT_DOC_BASE = "https://cdn.clinicaltrials.gov/large-docs"

# Additional 15 trials to try (to get at least 10 more successful)
TRIALS = [
    # More AstraZeneca trials
    {"nct_id": "NCT03170206", "name": "FLAURA2", "sponsor": "AstraZeneca", "condition": "NSCLC"},
    {"nct_id": "NCT02302807", "name": "SOLO1", "sponsor": "AstraZeneca", "condition": "OvarianCancer"},
    {"nct_id": "NCT01958021", "name": "POLO", "sponsor": "AstraZeneca", "condition": "PancreaticCancer"},

    # More Pfizer trials
    {"nct_id": "NCT03449446", "name": "JAVELIN_Bladder100", "sponsor": "Pfizer", "condition": "BladderCancer"},
    {"nct_id": "NCT02853318", "name": "KEYNOTE564", "sponsor": "Merck", "condition": "RenalCancer"},

    # More Roche/Genentech trials
    {"nct_id": "NCT02564263", "name": "IMPASSION130", "sponsor": "Roche", "condition": "TNBC"},
    {"nct_id": "NCT03434379", "name": "IMPOWER150", "sponsor": "Roche", "condition": "NSCLC"},

    # More Janssen trials
    {"nct_id": "NCT02912559", "name": "POLLUX", "sponsor": "Janssen", "condition": "MultipleMyeloma"},
    {"nct_id": "NCT02252172", "name": "ALCYONE", "sponsor": "Janssen", "condition": "MultipleMyeloma"},

    # GSK trials
    {"nct_id": "NCT02302755", "name": "COMBI_AD", "sponsor": "GSK", "condition": "Melanoma"},
    {"nct_id": "NCT02967692", "name": "DREAMM2", "sponsor": "GSK", "condition": "MultipleMyeloma"},

    # Novartis trials
    {"nct_id": "NCT02684006", "name": "MONALEESA2", "sponsor": "Novartis", "condition": "BreastCancer"},
    {"nct_id": "NCT03295981", "name": "COLUMBA", "sponsor": "Takeda", "condition": "MultipleMyeloma"},

    # Amgen trials
    {"nct_id": "NCT02609776", "name": "KYPROLIS", "sponsor": "Amgen", "condition": "MultipleMyeloma"},
    {"nct_id": "NCT02226965", "name": "FOURIER", "sponsor": "Amgen", "condition": "CVD"},
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
                "size": doc.get("size", 0),
                "date": doc.get("date", "")
            })
    except Exception as e:
        print(f"Error parsing documents: {e}")
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
        else:
            print(f"  Failed to download {filename}: HTTP {response.status_code}")
    except Exception as e:
        print(f"  Error downloading {filename}: {e}")
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
    except Exception as e:
        print(f"Error extracting sites: {e}")
    return sites


def create_sites_csv(sites, output_path, trial_name):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Site Number", "Site Name", "Country", "City", "State", "Zip", "Status"])
        for site in sites:
            writer.writerow([
                site["site_number"],
                site["facility"],
                site["country"],
                site["city"],
                site["state"],
                site["zip"],
                site["status"]
            ])
    return True


def process_trial(trial_info):
    nct_id = trial_info["nct_id"]
    name = trial_info["name"]
    folder_name = f"{nct_id}_{name}"

    print(f"\nProcessing {folder_name}...")

    trial_dir = OUTPUT_DIR / folder_name
    trial_dir.mkdir(parents=True, exist_ok=True)

    trial_data = get_trial_details(nct_id)
    if not trial_data:
        print(f"  Could not fetch trial details for {nct_id}")
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
                print(f"  Downloaded Protocol+SAP: {output_file.name}")
                protocol_downloaded = True
                sap_downloaded = True
        elif "protocol" in label and not protocol_downloaded:
            output_file = trial_dir / f"{folder_name}_Protocol.pdf"
            if download_document(nct_id, filename, output_file):
                print(f"  Downloaded Protocol: {output_file.name}")
                protocol_downloaded = True
        elif "statistical" in label or "sap" in label:
            output_file = trial_dir / f"{folder_name}_SAP.pdf"
            if download_document(nct_id, filename, output_file):
                print(f"  Downloaded SAP: {output_file.name}")
                sap_downloaded = True

    sites = extract_sites(trial_data)
    if sites:
        sites_file = trial_dir / f"{folder_name}_sites.csv"
        create_sites_csv(sites, sites_file, name)
        print(f"  Created sites file: {sites_file.name} ({len(sites)} sites)")
    else:
        print(f"  No site information available")

    if protocol_downloaded and sap_downloaded:
        print(f"  SUCCESS: {folder_name} - Protocol, SAP, and sites downloaded")
        return True
    elif protocol_downloaded or sap_downloaded:
        print(f"  PARTIAL: {folder_name} - Some documents downloaded")
        return True
    else:
        print(f"  WARNING: {folder_name} - No documents available for download")
        return False


def main():
    print("=" * 60)
    print("Clinical Trial Document Downloader - Batch 2")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    successful = 0
    needed = 10  # We need 10 more successful trials

    for trial in TRIALS:
        if successful >= needed:
            break
        try:
            if process_trial(trial):
                successful += 1
            time.sleep(1)
        except Exception as e:
            print(f"Error processing {trial['nct_id']}: {e}")

    print("\n" + "=" * 60)
    print(f"SUMMARY: {successful} successful trials downloaded")
    print("=" * 60)


if __name__ == "__main__":
    main()
