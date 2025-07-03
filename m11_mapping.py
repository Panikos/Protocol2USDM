"""Utility functions for loading and working with the USDM⇄M11 mapping workbook.

The excel file is maintained by CDISC and publicly hosted on GitHub.  By default we
load directly from the raw URL and cache the result so repeated calls are fast.
If you prefer to work offline, download the workbook and point `load_mapping()` to
a local path via the ``url`` argument.
"""
from functools import lru_cache
from typing import Dict, Tuple

import pandas as pd

# Raw link to the workbook (first sheet contains the mapping we need)
MAPPING_URL = (
    "https://raw.githubusercontent.com/cdisc-org/DDF-RA/main/Documents/Mappings/m11_mapping.xlsx"
)


@lru_cache(maxsize=1)
def load_mapping(url: str = MAPPING_URL) -> pd.DataFrame:  # pragma: no cover
    """Load the mapping workbook into a *single* DataFrame.

    Parameters
    ----------
    url : str, optional
        URL or local path to the workbook.  Defaults to the public GitHub raw link.

    Returns
    -------
    pandas.DataFrame
        The combined sheet as a DataFrame.
    """
    # ``openpyxl`` engine is required for *.xlsx* files.
    return pd.read_excel(url, sheet_name=0, engine="openpyxl")


def build_timepoint_map(df: pd.DataFrame) -> Dict[str, Tuple[str, str]]:
    """Return a dict mapping USDM **PlannedTimepoint name** → (visit, week/day).

    The mapping workbook contains separate columns for *Visit Label* and
    *Week/Day Label*.  We expose them so the Streamlit app can build the two-row
    M11 header easily.
    """
    col_candidates = [
        ("PlannedTimepointName", "VisitLabel", "WeekDayLabel"),
        ("plannedTimepointName", "visitLabel", "weekDayLabel"),  # fallbacks
    ]

    for pt_col, visit_col, wd_col in col_candidates:
        if {pt_col, visit_col, wd_col}.issubset(df.columns):
            return {
                str(row[pt_col]): (str(row[visit_col]), str(row[wd_col]))
                for _, row in df.iterrows()
                if pd.notna(row[pt_col])
            }

    # If required columns aren’t present we fall back to an empty mapping.
    return {}
