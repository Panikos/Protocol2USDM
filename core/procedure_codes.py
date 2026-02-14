"""
Procedure Code Enrichment Service.

Resolves procedure codes across multiple terminology systems using:
1. Embedded database of common clinical procedures (NCI, SNOMED, ICD-10, CPT, LOINC)
2. NCI EVS REST API for cross-terminology maps (online, cached)
3. Fallback to LLM-extracted code if no enrichment available

Modeled after the UnifiedTerminologyService in the USDM2Synthetic sister project,
adapted for Protocol2USDM's architecture (EVS client + CodeRegistry).

Usage:
    from core.procedure_codes import enrich_procedure_codes
    
    # Enrich a single procedure dict in-place
    enrich_procedure_codes(procedure_dict)
    
    # Or use the service directly
    svc = ProcedureCodeService()
    codes = svc.resolve("Venipuncture")
    # → [{"code": "C28221", "codeSystem": "NCI", ...}, {"code": "82078001", ...}, ...]
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ProcedureCodeEntry:
    """A single code for a procedure in one terminology system."""
    code: str
    code_system: str          # NCI, SNOMED, ICD-10, CPT, LOINC
    decode: str
    url: Optional[str] = None  # Browser URL for the code

    def to_dict(self) -> Dict[str, str]:
        d: Dict[str, str] = {
            "code": self.code,
            "codeSystem": self.code_system,
            "decode": self.decode,
        }
        if self.url:
            d["url"] = self.url
        return d


# ---------------------------------------------------------------------------
# Browser URL builders
# ---------------------------------------------------------------------------

_EVS_URL = "https://evsexplore.semantics.cancer.gov/evsexplore/concept/ncit"
_SNOMED_URL = "https://browser.ihtsdotools.org/?perspective=full&conceptId1="
_ICD10_URL = "https://icd.who.int/browse10/2019/en#/"
_LOINC_URL = "https://loinc.org/"

def _nci_url(code: str) -> str:
    return f"{_EVS_URL}/{code}"

def _snomed_url(code: str) -> str:
    return f"{_SNOMED_URL}{code}"

def _icd10_url(code: str) -> str:
    return f"{_ICD10_URL}{code}"

def _loinc_url(code: str) -> str:
    return f"{_LOINC_URL}{code}"


# ---------------------------------------------------------------------------
# Embedded procedure code database
# Common clinical procedures with codes from multiple systems.
# Follows the same pattern as USDM2Synthetic's SNOMED_CLINICAL_FINDINGS.
# ---------------------------------------------------------------------------

_PROCEDURE_DB: Dict[str, List[ProcedureCodeEntry]] = {}

def _add(name: str, *entries: ProcedureCodeEntry) -> None:
    """Register a procedure under one or more normalized keys."""
    key = name.lower().strip()
    _PROCEDURE_DB[key] = list(entries)

def _nci(code: str, decode: str) -> ProcedureCodeEntry:
    return ProcedureCodeEntry(code, "NCI", decode, _nci_url(code))

def _snomed(code: str, decode: str) -> ProcedureCodeEntry:
    return ProcedureCodeEntry(code, "SNOMED", decode, _snomed_url(code))

def _icd10(code: str, decode: str) -> ProcedureCodeEntry:
    return ProcedureCodeEntry(code, "ICD-10", decode, _icd10_url(code))

def _cpt(code: str, decode: str) -> ProcedureCodeEntry:
    return ProcedureCodeEntry(code, "CPT", decode)

def _loinc(code: str, decode: str) -> ProcedureCodeEntry:
    return ProcedureCodeEntry(code, "LOINC", decode, _loinc_url(code))


# ── Blood / Sample Collection ──────────────────────────────────────────────
_add("venipuncture",
     _nci("C28221", "Venipuncture"),
     _snomed("82078001", "Collection of blood specimen by venipuncture"),
     _cpt("36415", "Collection of venous blood by venipuncture"))
_add("blood draw",
     _nci("C28221", "Venipuncture"),
     _snomed("82078001", "Collection of blood specimen by venipuncture"),
     _cpt("36415", "Collection of venous blood by venipuncture"))
_add("blood collection",
     _nci("C28221", "Venipuncture"),
     _snomed("82078001", "Collection of blood specimen by venipuncture"),
     _cpt("36415", "Collection of venous blood by venipuncture"))
_add("urine collection",
     _nci("C62584", "Urine Specimen Collection"),
     _snomed("167217005", "Urine specimen collection"),
     _cpt("81050", "Urinalysis"))
_add("urinalysis",
     _nci("C49672", "Urinalysis"),
     _snomed("27171005", "Urinalysis"),
     _loinc("24356-8", "Urinalysis complete panel"),
     _cpt("81001", "Urinalysis"))
_add("biopsy",
     _nci("C17610", "Biopsy"),
     _snomed("86273004", "Biopsy"),
     _cpt("88305", "Tissue examination by pathologist"))
_add("bone marrow biopsy",
     _nci("C15189", "Bone Marrow Biopsy"),
     _snomed("274880004", "Bone marrow biopsy"),
     _cpt("38221", "Bone marrow biopsy"))
_add("lumbar puncture",
     _nci("C15327", "Lumbar Puncture"),
     _snomed("277762005", "Lumbar puncture"),
     _cpt("62270", "Lumbar puncture"))

# ── Cardiac / ECG ──────────────────────────────────────────────────────────
_add("electrocardiogram",
     _nci("C168186", "Electrocardiogram"),
     _snomed("29303009", "Electrocardiographic procedure"),
     _loinc("11524-6", "EKG study"),
     _cpt("93000", "Electrocardiogram complete"))
_add("ecg",
     _nci("C168186", "Electrocardiogram"),
     _snomed("29303009", "Electrocardiographic procedure"),
     _loinc("11524-6", "EKG study"),
     _cpt("93000", "Electrocardiogram complete"))
_add("12-lead ecg",
     _nci("C168186", "Electrocardiogram"),
     _snomed("268400002", "12-lead electrocardiogram"),
     _loinc("11524-6", "EKG study"),
     _cpt("93000", "Electrocardiogram complete"))
_add("echocardiogram",
     _nci("C38064", "Echocardiography"),
     _snomed("40701008", "Echocardiography"),
     _cpt("93306", "Echocardiography transthoracic"))
_add("holter monitor",
     _nci("C80404", "Holter Monitoring"),
     _snomed("164847006", "Holter electrocardiogram"),
     _cpt("93224", "Holter monitor"))

# ── Imaging ────────────────────────────────────────────────────────────────
_add("mri",
     _nci("C16809", "Magnetic Resonance Imaging"),
     _snomed("113091000", "Magnetic resonance imaging"),
     _cpt("70553", "MRI brain"))
_add("magnetic resonance imaging",
     _nci("C16809", "Magnetic Resonance Imaging"),
     _snomed("113091000", "Magnetic resonance imaging"),
     _cpt("70553", "MRI brain"))
_add("ct scan",
     _nci("C17204", "Computed Tomography"),
     _snomed("77477000", "Computerized axial tomography"),
     _cpt("74177", "CT abdomen and pelvis with contrast"))
_add("computed tomography",
     _nci("C17204", "Computed Tomography"),
     _snomed("77477000", "Computerized axial tomography"),
     _cpt("74177", "CT abdomen and pelvis with contrast"))
_add("x-ray",
     _nci("C38101", "X-Ray"),
     _snomed("363680008", "Radiographic imaging procedure"),
     _cpt("71046", "Chest X-ray"))
_add("chest x-ray",
     _nci("C38101", "X-Ray"),
     _snomed("399208008", "Plain chest X-ray"),
     _cpt("71046", "Chest X-ray 2 views"))
_add("pet scan",
     _nci("C17007", "Positron Emission Tomography"),
     _snomed("82918005", "Positron emission tomography"),
     _cpt("78816", "PET imaging"))
_add("ultrasound",
     _nci("C17230", "Ultrasonography"),
     _snomed("16310003", "Diagnostic ultrasonography"),
     _cpt("76700", "Ultrasound abdomen"))
_add("dexa scan",
     _nci("C48786", "Dual-Energy X-Ray Absorptiometry"),
     _snomed("312681000", "DXA scan"),
     _cpt("77080", "DXA bone density study"))

# ── Physical Assessments ───────────────────────────────────────────────────
_add("physical examination",
     _nci("C20989", "Physical Examination"),
     _snomed("5880005", "Physical examination procedure"),
     _cpt("99213", "Office visit established patient"))
_add("vital signs",
     _nci("C62103", "Vital Signs Measurement"),
     _snomed("118227000", "Vital signs finding"),
     _loinc("85353-1", "Vital signs panel"))
_add("vital signs measurement",
     _nci("C62103", "Vital Signs Measurement"),
     _snomed("118227000", "Vital signs finding"),
     _loinc("85353-1", "Vital signs panel"))
_add("blood pressure measurement",
     _nci("C49676", "Blood Pressure Measurement"),
     _snomed("46973005", "Blood pressure taking"),
     _loinc("85354-9", "Blood pressure panel"))
_add("body weight measurement",
     _nci("C25208", "Weight Measurement"),
     _snomed("39857003", "Body weight measure"),
     _loinc("29463-7", "Body weight"))
_add("height measurement",
     _nci("C25347", "Height"),
     _snomed("50373000", "Body height measure"),
     _loinc("8302-2", "Body height"))
_add("bmi measurement",
     _nci("C16358", "Body Mass Index"),
     _snomed("60621009", "Body mass index"),
     _loinc("39156-5", "Body mass index"))
_add("ophthalmologic examination",
     _nci("C62596", "Ophthalmologic Examination"),
     _snomed("36228007", "Ophthalmic examination"),
     _cpt("92002", "Eye exam new patient"))
_add("neurological examination",
     _nci("C62610", "Neurological Examination"),
     _snomed("84728005", "Neurological examination"),
     _cpt("95816", "EEG"))

# ── Laboratory Tests ───────────────────────────────────────────────────────
_add("complete blood count",
     _nci("C64765", "Complete Blood Count"),
     _snomed("26604007", "Complete blood count"),
     _loinc("57021-8", "CBC W Auto Differential panel"),
     _cpt("85025", "CBC with differential"))
_add("cbc",
     _nci("C64765", "Complete Blood Count"),
     _snomed("26604007", "Complete blood count"),
     _loinc("57021-8", "CBC W Auto Differential panel"),
     _cpt("85025", "CBC with differential"))
_add("chemistry panel",
     _nci("C62521", "Chemistry Panel"),
     _snomed("166312007", "Blood chemistry"),
     _loinc("24323-8", "Comprehensive metabolic panel"),
     _cpt("80053", "Comprehensive metabolic panel"))
_add("comprehensive metabolic panel",
     _nci("C62521", "Chemistry Panel"),
     _snomed("166312007", "Blood chemistry"),
     _loinc("24323-8", "Comprehensive metabolic panel"),
     _cpt("80053", "Comprehensive metabolic panel"))
_add("liver function test",
     _nci("C62613", "Liver Function Test"),
     _snomed("26958001", "Hepatic function panel"),
     _loinc("24325-3", "Hepatic function panel"),
     _cpt("80076", "Hepatic function panel"))
_add("renal function test",
     _nci("C62614", "Renal Function Test"),
     _snomed("444275007", "Renal function test"),
     _loinc("24362-6", "Renal function panel"),
     _cpt("80069", "Renal function panel"))
_add("coagulation panel",
     _nci("C62527", "Coagulation Test"),
     _snomed("302786002", "Coagulation screen"),
     _loinc("38875-1", "INR/PT panel"),
     _cpt("85610", "Prothrombin time"))
_add("thyroid function test",
     _nci("C62615", "Thyroid Function Test"),
     _snomed("36449004", "Thyroid function test"),
     _loinc("24348-5", "Thyroid function panel"),
     _cpt("84443", "TSH"))
_add("lipid panel",
     _nci("C62526", "Lipid Panel"),
     _snomed("252150008", "Lipid panel"),
     _loinc("24331-1", "Lipid panel"),
     _cpt("80061", "Lipid panel"))
_add("hba1c",
     _nci("C64849", "Hemoglobin A1c Measurement"),
     _snomed("43396009", "Hemoglobin A1c measurement"),
     _loinc("4548-4", "Hemoglobin A1c"),
     _cpt("83036", "Hemoglobin A1c"))
_add("hemoglobin a1c",
     _nci("C64849", "Hemoglobin A1c Measurement"),
     _snomed("43396009", "Hemoglobin A1c measurement"),
     _loinc("4548-4", "Hemoglobin A1c"),
     _cpt("83036", "Hemoglobin A1c"))
_add("pregnancy test",
     _nci("C62587", "Pregnancy Test"),
     _snomed("167252002", "Pregnancy test"),
     _loinc("2106-3", "Choriogonadotropin qualitative"),
     _cpt("81025", "Urine pregnancy test"))
_add("drug screen",
     _nci("C62531", "Drug Screening"),
     _snomed("171207006", "Screening for drug abuse"),
     _loinc("8246-1", "Drug screen panel"),
     _cpt("80307", "Drug screen"))
_add("serum creatinine",
     _nci("C64547", "Serum Creatinine Measurement"),
     _snomed("113075003", "Serum creatinine measurement"),
     _loinc("2160-0", "Creatinine in serum or plasma"),
     _cpt("82565", "Creatinine"))

# ── Therapeutic Procedures ─────────────────────────────────────────────────
_add("infusion",
     _nci("C15388", "Infusion"),
     _snomed("14152002", "Infusion"),
     _cpt("96365", "IV infusion first hour"))
_add("intravenous infusion",
     _nci("C15388", "Infusion"),
     _snomed("14152002", "Infusion"),
     _cpt("96365", "IV infusion first hour"))
_add("injection",
     _nci("C38299", "Injection"),
     _snomed("28289002", "Injection"),
     _cpt("96372", "Therapeutic injection"))
_add("subcutaneous injection",
     _nci("C38299", "Injection"),
     _snomed("473188004", "Subcutaneous injection"),
     _cpt("96372", "Therapeutic injection SC"))
_add("intramuscular injection",
     _nci("C38299", "Injection"),
     _snomed("76601001", "Intramuscular injection"),
     _cpt("96372", "Therapeutic injection IM"))
_add("blood transfusion",
     _nci("C15192", "Blood Transfusion"),
     _snomed("116859006", "Transfusion of blood product"),
     _cpt("36430", "Transfusion of blood"))

# ── Monitoring ─────────────────────────────────────────────────────────────
_add("pulse oximetry",
     _nci("C62618", "Pulse Oximetry"),
     _snomed("104847001", "Oxygen saturation measurement"),
     _loinc("59408-5", "Oxygen saturation by pulse oximetry"),
     _cpt("94760", "Pulse oximetry"))
_add("telemetry",
     _nci("C62620", "Telemetry Monitoring"),
     _snomed("258104002", "Continuous cardiac monitoring"),
     _cpt("93040", "Rhythm ECG"))
_add("spirometry",
     _nci("C38080", "Spirometry"),
     _snomed("127783003", "Spirometry"),
     _loinc("19923-6", "FEV1"),
     _cpt("94010", "Spirometry"))
_add("pulmonary function test",
     _nci("C38080", "Spirometry"),
     _snomed("23426006", "Measurement of respiratory function"),
     _cpt("94010", "Spirometry"))
_add("electroencephalogram",
     _nci("C38064", "Electroencephalogram"),
     _snomed("54550000", "Electroencephalogram"),
     _cpt("95819", "EEG extended"))
_add("eeg",
     _nci("C38064", "Electroencephalogram"),
     _snomed("54550000", "Electroencephalogram"),
     _cpt("95819", "EEG extended"))

# ── Other ──────────────────────────────────────────────────────────────────
_add("informed consent",
     _nci("C16735", "Informed Consent"),
     _snomed("182891005", "Informed consent for procedure"))
_add("randomization",
     _nci("C15417", "Randomization"),
     _snomed("182891005", "Randomization procedure"))
_add("skin test",
     _nci("C62619", "Skin Test"),
     _snomed("252484000", "Skin test"),
     _cpt("86580", "Skin test"))
_add("suture removal",
     _nci("C62592", "Suture Removal"),
     _snomed("30549001", "Removal of suture"),
     _cpt("15850", "Removal of sutures"))


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class ProcedureCodeService:
    """
    Resolves procedure names to codes across multiple terminology systems.
    
    Priority: embedded DB → EVS API maps → LLM-extracted code passthrough.
    """

    def __init__(self, use_evs: bool = True):
        self._use_evs = use_evs

    def resolve(self, name: str) -> List[Dict[str, str]]:
        """
        Resolve a procedure name to all available coded representations.
        
        Returns list of code dicts: [{"code": "...", "codeSystem": "...", "decode": "...", "url": "..."}, ...]
        """
        entries = self._lookup_embedded(name)
        if entries:
            return [e.to_dict() for e in entries]

        # Fallback: try EVS search if enabled
        if self._use_evs:
            evs_entries = self._lookup_evs(name)
            if evs_entries:
                return [e.to_dict() for e in evs_entries]

        return []

    def _lookup_embedded(self, name: str) -> List[ProcedureCodeEntry]:
        """Look up in the embedded procedure code database."""
        key = name.lower().strip()
        if not key or len(key) < 2:
            return []
        
        # Exact match
        if key in _PROCEDURE_DB:
            return _PROCEDURE_DB[key]

        # Try without common suffixes/prefixes
        for strip in ["measurement", "procedure", "test", "examination",
                       "collection", "assessment", "monitoring"]:
            trimmed = key.replace(strip, "").strip()
            if trimmed and len(trimmed) >= 3 and trimmed in _PROCEDURE_DB:
                return _PROCEDURE_DB[trimmed]

        # Fuzzy: check if any DB key is contained in the name or vice versa
        for db_key, entries in _PROCEDURE_DB.items():
            if db_key in key or (len(key) >= 3 and key in db_key):
                return entries
            # Also match on decode from the first entry
            if entries and len(key) >= 3 and key in entries[0].decode.lower():
                return entries

        return []

    def _lookup_evs(self, name: str) -> List[ProcedureCodeEntry]:
        """Look up via NCI EVS REST API with ?include=maps."""
        try:
            from core.evs_client import get_client
            client = get_client()

            # Search NCIt for the procedure name
            results = client.search_term(name, limit=3)
            if not results:
                return []

            nci_code = results[0].get("code", "")
            nci_name = results[0].get("name", name)
            if not nci_code:
                return []

            entries = [ProcedureCodeEntry(nci_code, "NCI", nci_name, _nci_url(nci_code))]

            # Fetch cross-terminology maps
            data = client._http_get(
                f"https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/{nci_code}",
                {"include": "maps"},
            )
            if data:
                seen: set = set()
                for m in data.get("maps", []):
                    target_code = m.get("targetCode", "")
                    target_name = m.get("targetName", "")
                    target_term = m.get("targetTermGroup", "")
                    target_tgy = m.get("targetTerminology", "")

                    if not target_code or target_code in seen:
                        continue
                    seen.add(target_code)

                    if "SNOMED" in target_tgy.upper() or "SCT" in target_tgy.upper():
                        entries.append(_snomed(target_code, target_name or nci_name))
                    elif "ICD" in target_tgy.upper():
                        entries.append(_icd10(target_code, target_name or nci_name))
                    elif "CPT" in target_tgy.upper() or "HCPCS" in target_tgy.upper():
                        entries.append(_cpt(target_code, target_name or nci_name))
                    elif "LOINC" in target_tgy.upper() or "LNC" in target_tgy.upper():
                        entries.append(_loinc(target_code, target_name or nci_name))

            return entries
        except Exception as e:
            logger.debug(f"EVS procedure lookup failed for '{name}': {e}")
            return []


# ---------------------------------------------------------------------------
# Singleton + convenience
# ---------------------------------------------------------------------------

_service: Optional[ProcedureCodeService] = None


def get_service() -> ProcedureCodeService:
    global _service
    if _service is None:
        _service = ProcedureCodeService()
    return _service


def enrich_procedure_codes(procedure: Dict[str, Any]) -> None:
    """
    Enrich a USDM Procedure dict in-place with multi-system codes.
    
    Adds an extensionAttribute ``x-procedureCodes`` containing an array
    of ``{code, codeSystem, decode, url}`` dicts from all resolved systems.
    
    The primary ``code`` field is also upgraded to the best NCI code if one
    was found and the current code is from a lower-priority system.
    """
    name = procedure.get("name", "")
    if not name:
        return

    svc = get_service()
    codes = svc.resolve(name)
    if not codes:
        return

    # Store all codes in extension
    exts = procedure.setdefault("extensionAttributes", [])
    # Avoid duplicates
    already = any(
        e.get("url", "").endswith("x-procedureCodes") for e in exts
    )
    if already:
        return

    import uuid
    exts.append({
        "id": str(uuid.uuid4()),
        "url": "https://protocol2usdm.io/extensions/x-procedureCodes",
        "instanceType": "ExtensionAttribute",
        "value": codes,
    })

    # Upgrade primary code to NCI if current is lower-priority
    nci_code = next((c for c in codes if c["codeSystem"] == "NCI"), None)
    if nci_code:
        current = procedure.get("code", {})
        current_system = (current.get("codeSystem", "") or "").upper()
        if current_system in ("CPT", "CURRENT PROCEDURAL", "") or not current.get("code"):
            procedure["code"] = {
                "id": current.get("id") or str(uuid.uuid4()),
                "code": nci_code["code"],
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "",
                "decode": nci_code["decode"],
                "instanceType": "Code",
            }

    logger.debug(f"Enriched procedure '{name}' with {len(codes)} codes")
