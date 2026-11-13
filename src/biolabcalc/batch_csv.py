"""Zero-dependency CSV and TSV batch processing utility for high-throughput sequence calculations."""

from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Optional, Tuple

from .molecular_weight import calculate_dna_mw, calculate_protein_mw, calculate_rna_mw
from .protein import calculate_extinction_coefficient
from .seq_utils import clean_sequence
from .spectroscopy import calculate_nucleic_acid_e260


def _detect_delimiter(filepath: str, sample_text: str) -> str:
    """Detect CSV/TSV delimiter based on extension or content."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".tsv":
        return "\t"
    if ext == ".csv":
        return ","
    if "\t" in sample_text and sample_text.count("\t") > sample_text.count(","):
        return "\t"
    return ","


def _auto_detect_seq_type(cleaned_seq: str) -> str:
    """Infer whether a sequence is DNA, RNA, or Protein based on its character set."""
    s = cleaned_seq.upper().replace("*", "")
    if not s:
        return "dna"
    chars = set(s)
    if chars.issubset(set("ACGTN")):
        return "dna"
    if chars.issubset(set("ACGUN")):
        return "rna"
    if "U" in chars and not set("T").intersection(chars):
        return "rna"
    return "protein"


def process_batch_csv(
    input_path: str,
    output_path: str,
    delimiter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a CSV or TSV file containing sequences, calculate biophysical properties,
    and write an annotated output CSV/TSV.

    Parameters
    ----------
    input_path : str
        Path to input CSV or TSV file.
    output_path : str
        Destination path for annotated results.
    delimiter : str, optional
        Explicit delimiter (e.g., ',' or '\t'). If None, auto-detected.

    Returns
    -------
    dict
        Execution summary metrics (total_rows, success_count, error_count, output_path).
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8-sig") as f:
        sample_header = f.read(2048)
        f.seek(0)
        delim = delimiter or _detect_delimiter(input_path, sample_header)
        reader = list(csv.reader(f, delimiter=delim))

    if not reader:
        raise ValueError(f"Batch file '{input_path}' is completely empty.")

    header_row = [h.strip() for h in reader[0]]

    # Identify key column indices
    seq_col = -1
    id_col = -1
    type_col = -1

    for idx, col_name in enumerate(header_row):
        col_lower = col_name.lower().replace(" ", "_")
        if seq_col == -1 and col_lower in ("sequence", "seq", "oligo", "peptide", "nucleotide", "input"):
            seq_col = idx
        elif id_col == -1 and col_lower in ("id", "name", "label", "sample", "oligo_name", "seq_id", "sample_id"):
            id_col = idx
        elif type_col == -1 and col_lower in ("type", "seq_type", "molecule", "mol_type", "biomolecule"):
            type_col = idx

    # If sequence column is not found by name, default to the second column or first column
    if seq_col == -1:
        if len(header_row) >= 2 and any(c in header_row[1].upper() for c in ("A", "C", "G", "T")):
            seq_col = 1
        else:
            seq_col = 0

    out_delimiter = delimiter or _detect_delimiter(output_path, "")
    output_headers = list(header_row) + [
        "Clean_Sequence",
        "Sequence_Type",
        "Length_bp_aa",
        "Molecular_Weight_Da",
        "GC_Content_Pct",
        "Extinction_Coeff",
        "Processing_Status",
    ]

    out_rows = [output_headers]
    success_count = 0
    error_count = 0

    for r_idx, row in enumerate(reader[1:], start=2):
        if not row or not any(row):
            continue

        raw_seq = row[seq_col].strip() if seq_col < len(row) else ""
        explicit_type = row[type_col].strip().lower() if (type_col != -1 and type_col < len(row)) else ""

        if not raw_seq:
            padded_row = list(row) + ["", "", 0, 0.0, 0.0, 0, "EMPTY_SEQUENCE"]
            out_rows.append(padded_row)
            continue

        try:
            cleaned = clean_sequence(raw_seq)
            st = explicit_type or _auto_detect_seq_type(cleaned)
            length = len(cleaned)

            if "rna" in st:
                mw_res = calculate_rna_mw(cleaned)
                mw = round(mw_res.average_mw, 2)
                gc = mw_res.gc_content
                e_coeff = calculate_nucleic_acid_e260(cleaned, seq_type="rna")
                mol_label = "RNA"
            elif "prot" in st or "aa" in st or "peptide" in st:
                mw_res = calculate_protein_mw(cleaned)
                mw = round(mw_res.average_mw, 2)
                gc = 0.0
                ext_res = calculate_extinction_coefficient(cleaned)
                e_coeff = ext_res.extinction_coeff_m_cm
                mol_label = "PROTEIN"
            else:
                # DNA
                mw_res = calculate_dna_mw(cleaned, double_stranded=False)
                mw = round(mw_res.average_mw, 2)
                gc = mw_res.gc_content
                e_coeff = calculate_nucleic_acid_e260(cleaned, seq_type="dna")
                mol_label = "DNA"

            padded_row = list(row) + [cleaned, mol_label, length, mw, gc, e_coeff, "OK"]
            success_count += 1
        except Exception as e:
            error_count += 1
            padded_row = list(row) + [raw_seq, "UNKNOWN", len(raw_seq), 0.0, 0.0, 0, f"ERROR: {e}"]

        out_rows.append(padded_row)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=out_delimiter)
        writer.writerows(out_rows)

    return {
        "input_path": input_path,
        "output_path": output_path,
        "delimiter": out_delimiter,
        "total_rows": len(reader) - 1,
        "success_count": success_count,
        "error_count": error_count,
    }
