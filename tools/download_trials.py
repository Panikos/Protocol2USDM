#!/usr/bin/env python3
"""
Download Protocol and SAP documents from ClinicalTrials.gov for specified trials.
Creates folder structure with proper naming convention.
"""

import os
import json
import csv
import requests
import time
from pathlib import Path

# Base paths
OUTPUT_DIR = Path(r"C:\Users\panik\Documents\GitHub\Protcol2USDMv3\input\trial")
CT_API_BASE = "https://clinicaltrials.gov/api/v2/studies"
CT_DOC_BASE = "https://cdn.clinicaltrials.gov/large-docs"

# List of 30 trials to download (excluding the 5 we already have)
TRIALS = [
    # Pfizer trials
    {"nct_id": "NCT03627767", "name": "JADE_MONO2", "sponsor": "Pfizer", "condition": "AtopicDermatitis"},
    {"nct_id": "NCT04368728", "name": "EPIC_HR", "sponsor": "Pfizer", "condition": "COVID19"},
    {"nct_id": "NCT04816643", "name": "PAXLOVID", "sponsor": "Pfizer", "condition": "COVID19"},
    {"nct_id": "NCT03760146", "name": "JADE_COMPARE", "sponsor": "Pfizer", "condition": "AtopicDermatitis"},
    {"nct_id": "NCT04564716", "name": "COMIRNATY", "sponsor": "Pfizer", "condition": "COVID19"},

    # Roche/Genentech trials
    {"nct_id": "NCT04740905", "name": "BALATON", "sponsor": "Roche", "condition": "BRVO"},
    {"nct_id": "NCT02908672", "name": "TRILOGY", "sponsor": "Roche", "condition": "Melanoma"},
    {"nct_id": "NCT03125902", "name": "IMPASSION131", "sponsor": "Roche", "condition": "TNBC"},
    {"nct_id": "NCT02053610", "name": "CLL11", "sponsor": "Roche", "condition": "CLL"},
    {"nct_id": "NCT04028050", "name": "IMPOWER133CN", "sponsor": "Roche", "condition": "SCLC"},

    # AbbVie trials
    {"nct_id": "NCT03104374", "name": "SELECT_PsA2", "sponsor": "AbbVie", "condition": "PsA"},
    {"nct_id": "NCT02706951", "name": "SELECT_MONO", "sponsor": "AbbVie", "condition": "RA"},
    {"nct_id": "NCT01931670", "name": "ELARIS_EM1", "sponsor": "AbbVie", "condition": "Endometriosis"},
    {"nct_id": "NCT02163694", "name": "BROCADE3", "sponsor": "AbbVie", "condition": "BreastCancer"},
    {"nct_id": "NCT03781167", "name": "ABBV951", "sponsor": "AbbVie", "condition": "Parkinsons"},

    # Sanofi trials
    {"nct_id": "NCT02023879", "name": "ODYSSEY_CHOICE2", "sponsor": "Sanofi", "condition": "Hypercholesterolemia"},
    {"nct_id": "NCT04161495", "name": "XTEND_1", "sponsor": "Sanofi", "condition": "HemophiliaA"},
    {"nct_id": "NCT04410991", "name": "GEMINI2", "sponsor": "Sanofi", "condition": "MS"},
    {"nct_id": "NCT03347396", "name": "CARDINAL", "sponsor": "Sanofi", "condition": "ColdAgglutinin"},
    {"nct_id": "NCT01373281", "name": "CYD14", "sponsor": "Sanofi", "condition": "Dengue"},

    # Janssen/J&J trials
    {"nct_id": "NCT02065791", "name": "CREDENCE", "sponsor": "Janssen", "condition": "DKD"},
    {"nct_id": "NCT02407236", "name": "UNIFI", "sponsor": "Janssen", "condition": "UC"},
    {"nct_id": "NCT01776840", "name": "SHINE", "sponsor": "Janssen", "condition": "MCL"},
    {"nct_id": "NCT02493868", "name": "SUSTAIN1", "sponsor": "Janssen", "condition": "TRD"},
    {"nct_id": "NCT01081769", "name": "PROSIPAL", "sponsor": "Janssen", "condition": "Schizophrenia"},

    # Additional major trials from other top pharma
    {"nct_id": "NCT03461952", "name": "EMPEROR_Reduced", "sponsor": "BI", "condition": "HeartFailure"},
    {"nct_id": "NCT03057977", "name": "DAPA_HF", "sponsor": "AstraZeneca", "condition": "HeartFailure"},
    {"nct_id": "NCT02535078", "name": "DECLARE_TIMI58", "sponsor": "AstraZeneca", "condition": "T2DM"},
    {"nct_id": "NCT03036124", "name": "ADAURA", "sponsor": "AstraZeneca", "condition": "NSCLC"},
    {"nct_id": "NCT02677896", "name": "SPARTAN", "sponsor": "Janssen", "condition": "ProstateCancer"},
]


def get_trial_details(nct_id):
    """Fetch trial details from ClinicalTrials.gov API"""
    url = f"{CT_API_BASE}/{nct_id}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching {nct_id}: {e}")
    return None


def get_document_info(trial_data):
    """Extract document information from trial data"""
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
    """Download a document from ClinicalTrials.gov CDN"""
    # Extract the last 2 digits of NCT ID for folder structure
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
    """Extract site information from trial data"""
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
    """Create a CSV file with site information"""
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
    """Process a single trial - fetch details, download docs, create sites file"""
    nct_id = trial_info["nct_id"]
    name = trial_info["name"]
    folder_name = f"{nct_id}_{name}"

    print(f"\nProcessing {folder_name}...")

    # Create output folder
    trial_dir = OUTPUT_DIR / folder_name
    trial_dir.mkdir(parents=True, exist_ok=True)

    # Fetch trial details
    trial_data = get_trial_details(nct_id)
    if not trial_data:
        print(f"  Could not fetch trial details for {nct_id}")
        return False

    # Get document info
    docs = get_document_info(trial_data)

    # Download documents
    protocol_downloaded = False
    sap_downloaded = False

    for doc in docs:
        label = doc["label"].lower()
        filename = doc["filename"]

        if "protocol" in label and "sap" in label:
            # Combined Protocol_SAP document
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

    # Extract and save sites
    sites = extract_sites(trial_data)
    if sites:
        sites_file = trial_dir / f"{folder_name}_sites.csv"
        create_sites_csv(sites, sites_file, name)
        print(f"  Created sites file: {sites_file.name} ({len(sites)} sites)")
    else:
        print(f"  No site information available")

    # Summary
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
    """Main function to process all trials"""
    print("=" * 60)
    print("Clinical Trial Document Downloader")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    successful = 0
    failed = 0

    for trial in TRIALS:
        try:
            if process_trial(trial):
                successful += 1
            else:
                failed += 1
            # Rate limiting
            time.sleep(1)
        except Exception as e:
            print(f"Error processing {trial['nct_id']}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"SUMMARY: {successful} successful, {failed} failed out of {len(TRIALS)} trials")
    print("=" * 60)


if __name__ == "__main__":
    main()
