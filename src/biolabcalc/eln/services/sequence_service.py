"""
Module: biolabcalc.eln.services.sequence_service
Component: Biological Sequence Registry & Biophysical Property Computation Engine
Architectural Role: Core service providing registration, storage, and automated biophysical property
calculations (Tm, GC%, MW, pI, e280, A0.1%) for primers, plasmids, aptamers, and protein constructs.
"""

from __future__ import annotations

import math
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ...molecular_weight import calculate_dna_mw, calculate_protein_mw, calculate_rna_mw
from ...protein import calculate_extinction_coefficient
from ...seq_utils import calculate_gc_content, clean_sequence, count_bases
from .audit_service import get_audit_service

# EMBOSS / Bjellqvist pKa values for amino acid side chains and termini
PKA_VALUES: Dict[str, float] = {
    "N_term": 8.6,
    "C_term": 3.6,
    "C": 8.5,
    "D": 3.9,
    "E": 4.1,
    "H": 6.5,
    "K": 10.8,
    "R": 12.5,
    "Y": 10.1,
}


def calculate_isoelectric_point(amino_acid_sequence: str, precision: float = 0.001) -> float:
    """
    Calculate the theoretical isoelectric point (pI) of a protein using the Henderson-Hasselbalch
    bisection method.

    Formula:
        Net charge Q(pH) = Sum(Positively charged groups) - Sum(Negatively charged groups)
        Positively charged: N-term, Lys (K), Arg (R), His (H) => 1 / (1 + 10^(pH - pKa))
        Negatively charged: C-term, Asp (D), Glu (E), Cys (C), Tyr (Y) => 1 / (1 + 10^(pKa - pH))
        Bisection algorithm locates the root Q(pI) = 0.

    Parameter amino_acid_sequence (str): Single-letter amino acid sequence.
    Parameter precision (float): Bisection convergence tolerance (default: 0.001).
    Return Type: float (rounded to 2 decimal places).
    """
    seq = re.sub(r"[^A-Za-z]", "", amino_acid_sequence).upper()
    if not seq:
        return 7.0

    counts = count_bases(seq)
    n_k = counts.get("K", 0)
    n_r = counts.get("R", 0)
    n_h = counts.get("H", 0)
    n_d = counts.get("D", 0)
    n_e = counts.get("E", 0)
    n_c = counts.get("C", 0)
    n_y = counts.get("Y", 0)

    def net_charge(ph: float) -> float:
        # Positive groups
        pos = (
            (1.0 / (1.0 + 10.0 ** (ph - PKA_VALUES["N_term"])))
            + n_k * (1.0 / (1.0 + 10.0 ** (ph - PKA_VALUES["K"])))
            + n_r * (1.0 / (1.0 + 10.0 ** (ph - PKA_VALUES["R"])))
            + n_h * (1.0 / (1.0 + 10.0 ** (ph - PKA_VALUES["H"])))
        )
        # Negative groups
        neg = (
            (1.0 / (1.0 + 10.0 ** (PKA_VALUES["C_term"] - ph)))
            + n_d * (1.0 / (1.0 + 10.0 ** (PKA_VALUES["D"] - ph)))
            + n_e * (1.0 / (1.0 + 10.0 ** (PKA_VALUES["E"] - ph)))
            + n_c * (1.0 / (1.0 + 10.0 ** (PKA_VALUES["C"] - ph)))
            + n_y * (1.0 / (1.0 + 10.0 ** (PKA_VALUES["Y"] - ph)))
        )
        return pos - neg

    low = 0.0
    high = 14.0
    while (high - low) > precision:
        mid = (low + high) / 2.0
        charge = net_charge(mid)
        if charge > 0:
            low = mid
        else:
            high = mid

    return round((low + high) / 2.0, 2)


def calculate_primer_tm(dna_sequence: str) -> float:
    """
    Calculate oligonucleotide melting temperature Tm in Celsius using standard nearest-neighbor / Wallace formulas.

    Parameter dna_sequence (str): Clean nucleotide sequence.
    Return Type: float (rounded to 1 decimal place).
    """
    seq = re.sub(r"[^A-Za-z]", "", dna_sequence).upper()
    length = len(seq)
    if length == 0:
        return 0.0

    counts = count_bases(seq)
    a_count = counts.get("A", 0)
    t_count = counts.get("T", 0)
    g_count = counts.get("G", 0)
    c_count = counts.get("C", 0)

    if length < 14:
        # Wallace Rule: Tm = 2*(A+T) + 4*(G+C)
        tm = 2.0 * (a_count + t_count) + 4.0 * (g_count + c_count)
    else:
        # Marmur-Schildkraut-Doty / SantaLucia empirical formula (50 mM Na+)
        gc_pct = (g_count + c_count) / length * 100.0
        tm = 64.9 + 41.0 * (g_count + c_count - 16.4) / length

    return round(tm, 1)


@dataclass
class SequenceEntity:
    """
    Data model representing a registered biological sequence entity.

    Architectural Role: Canonical registry record storing nucleotide or amino acid sequences,
    classification, and biophysical properties.
    """

    entity_id: str
    name: str
    entity_type: str  # primer, plasmid, aptamer, protein_construct
    sequence: str
    description: str
    length: int
    molecular_weight_da: float
    gc_percent: Optional[float] = None
    melting_temp_c: Optional[float] = None
    isoelectric_point: Optional[float] = None
    extinction_coeff_m_cm: Optional[int] = None
    absorbance_01_pct: Optional[float] = None  # A0.1% (1 mg/mL)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_by: str = "unknown"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize sequence entity to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


class SequenceService:
    """
    Service managing construct registry and biophysical sequence calculations.

    Architectural Role: Manages persistent registry of biological materials, automates thermodynamic
    and spectrophotometric calculations, and provides lookup endpoints.
    """

    def __init__(self) -> None:
        """
        Initialize SequenceService and pre-seed core laboratory constructs (e.g. pET-28a-T7RNAP).

        """
        self._lock = threading.RLock()
        self._registry: Dict[str, SequenceEntity] = {}
        self._audit_service = get_audit_service()
        self._seed_standard_constructs()

    def _seed_standard_constructs(self) -> None:
        """
        Pre-seed standard constructs including His-tagged T7 RNA Polymerase and sequencing primers.

        """
        # Full amino acid sequence for pET-28a-T7RNAP (His6-Thrombin-T7RNAP, 883 aa)
        t7rnap_aa = (
            "MGSSHHHHHHSSGLVPRGSHMNTINIAKNDFSDIELAAIPFNTLADHYGERLAREQLALEHESYEMGEARFRKMFERQL"
            "KAGEVADNAAAKPLITTLLPKMIARINDWFEEVKAKRGKRPTAFQFLQEIKPEAVAYITIKTTLACLTSADNTTVQAV"
            "ASAIGRAIEDEARFGRIRDLEAKHFKKNVEEQLNKRVGHVYKKAFMQVVEADMLSKGLLGGEAWSSWHKEDSIHVGVRC"
            "IEMLIESTGMVSLHRQNAGVVGQDSETIELAPEYAEAIATRAGALAGISPMFQPCVVPPKPWTGITGGGYWANGRRPLA"
            "LVRTHSKKALMRYEDVYMPEVYKAINIAQNTAWKINKKVLAVANVITKWKHCPVEDIPAIEREELPMKPEDIDMNPEAL"
            "TAWKRAAAAVYRKDKARKSRRISLEFMLEQANKFANHKAIWFPYNMDWRGRVYAVSMFNPQGNDMTKGLLTLAKGKPIG"
            "KEGYYWLKIHGANCAGVDKVPFPERIKFIEENHENIMACAKSPLENTWWAEQDSPFCFLAFCFEYAGVQHHGLSYNCSL"
            "PLAFDGSCSGIQHFSAMLRDEVGGRAVNLLPSETVQDIYGIVAKKVNEILQADAINGTDNEVVTVTDENTGEISEKVKL"
            "GTKALAGQWLAYGVTRSVTKRSVMTLAYGSKEFGFRQQVLEDTIQPAIDSGKGLMFTQPNQAAGYMAKLIWESVSVTVV"
            "AAVEAMNWLKSAAKLLAAEVKDKKTGEILRKRCAVHWVTPDGFPVWQEYKKPIQTRLNLMFLGQFRLQPTINTNKDSEI"
            "DAHKQESGIAPNFVHSQDGSHLRKTVVWAHEKYGIESFALIHDSFGTIPADAANLFKAVRETMVDTYESCDVLADFYDQ"
            "FADQLHESQLDKMPALPAKGNLNLRDILESDFAFA"
        )
        self.register_sequence(
            entity_id="pET-28a-T7RNAP",
            name="pET-28a Recombinant T7 RNA Polymerase (N-term 6xHis)",
            entity_type="protein_construct",
            sequence=t7rnap_aa,
            description="Recombinant bacteriophage T7 RNA Polymerase expressed with N-terminal 6xHis tag from pET-28a vector.",
            tags=["T7RNAP", "Expression", "IVT", "His-tag"],
            created_by="pi_admin",
        )

        # Standard T7 promoter primer
        self.register_sequence(
            entity_id="PRIMER-T7-FWD",
            name="T7 Promoter Primer",
            entity_type="primer",
            sequence="TAATACGACTCACTATAGGG",
            description="Universal sequencing and PCR forward primer for T7 promoter region.",
            tags=["Sequencing", "PCR", "T7"],
            created_by="pi_admin",
        )

        # Standard T7 terminator primer
        self.register_sequence(
            entity_id="PRIMER-T7-REV",
            name="T7 Terminator Primer",
            entity_type="primer",
            sequence="GCTAGTTATTGCTCAGCGG",
            description="Universal sequencing and PCR reverse primer for T7 terminator region.",
            tags=["Sequencing", "PCR", "T7"],
            created_by="pi_admin",
        )

    def calculate_properties(
        self,
        sequence: str,
        entity_type: str,
    ) -> Dict[str, Any]:
        """
        Compute biophysical, thermodynamic, and spectrophotometric properties for a given sequence.

        Parameter sequence (str): Raw sequence string.
        Parameter entity_type (str): Classification ('primer', 'plasmid', 'aptamer', 'protein_construct').
        Return Type: Dict[str, Any]
        """
        cleaned = clean_sequence(sequence)
        length = len(cleaned)
        if length == 0:
            return {"length": 0, "molecular_weight_da": 0.0}

        res: Dict[str, Any] = {"length": length}

        if entity_type == "protein_construct":
            mw_obj = calculate_protein_mw(cleaned)
            mw_da = mw_obj.average_mw
            ext_obj = calculate_extinction_coefficient(cleaned)
            pi_val = calculate_isoelectric_point(cleaned)

            e280 = ext_obj.extinction_coeff_m_cm
            a01 = round(e280 / mw_da, 3) if mw_da > 0 else 0.0

            res.update(
                {
                    "molecular_weight_da": round(mw_da, 2),
                    "molecular_weight_kda": round(mw_da / 1000.0, 2),
                    "isoelectric_point": pi_val,
                    "extinction_coeff_m_cm": e280,
                    "absorbance_01_pct": a01,
                    "tryptophan_count": ext_obj.tryptophan_count,
                    "tyrosine_count": ext_obj.tyrosine_count,
                    "cysteine_count": count_bases(cleaned).get("C", 0),
                }
            )

        elif entity_type in ("primer", "plasmid"):
            # DNA sequence
            is_ss = entity_type == "primer"
            mw_obj = calculate_dna_mw(cleaned, double_stranded=(not is_ss))
            mw_da = mw_obj.average_mw
            gc_pct = calculate_gc_content(cleaned)
            tm_c = calculate_primer_tm(cleaned)

            res.update(
                {
                    "molecular_weight_da": round(mw_da, 2),
                    "gc_percent": gc_pct,
                    "melting_temp_c": tm_c,
                }
            )

        elif entity_type == "aptamer":
            # RNA sequence
            mw_obj = calculate_rna_mw(cleaned)
            mw_da = mw_obj.average_mw
            gc_pct = calculate_gc_content(cleaned)

            res.update(
                {
                    "molecular_weight_da": round(mw_da, 2),
                    "gc_percent": gc_pct,
                }
            )

        return res

    def register_sequence(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        sequence: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: str = "unknown",
    ) -> SequenceEntity:
        """
        Register a new sequence construct and compute its physicochemical profile.

        Parameter entity_id (str): Unique construct identifier (e.g. pET-28a-T7RNAP).
        Parameter name (str): Descriptive label.
        Parameter entity_type (str): 'primer', 'plasmid', 'aptamer', or 'protein_construct'.
        Parameter sequence (str): Nucleotide or amino acid sequence string.
        Parameter description (str): Background notes.
        Parameter tags (Optional[List[str]]): Categorical search tags.
        Parameter metadata (Optional[Dict[str, Any]]): Custom metadata.
        Parameter created_by (str): Operator ID.
        Return Type: SequenceEntity
        """
        with self._lock:
            cleaned = clean_sequence(sequence)
            props = self.calculate_properties(cleaned, entity_type)
            now_iso = datetime.now(timezone.utc).isoformat()

            entity = SequenceEntity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                sequence=cleaned,
                description=description,
                length=props.get("length", len(cleaned)),
                molecular_weight_da=props.get("molecular_weight_da", 0.0),
                gc_percent=props.get("gc_percent"),
                melting_temp_c=props.get("melting_temp_c"),
                isoelectric_point=props.get("isoelectric_point"),
                extinction_coeff_m_cm=props.get("extinction_coeff_m_cm"),
                absorbance_01_pct=props.get("absorbance_01_pct"),
                tags=tags or [],
                metadata=metadata or {},
                created_by=created_by,
                created_at=now_iso,
            )
            self._registry[entity_id] = entity

            self._audit_service.record_event(
                entity_type="sequence",
                entity_id=entity_id,
                action="REGISTER",
                performed_by=created_by,
                previous_state=None,
                new_state=entity.to_dict(),
                metadata={"entity_type": entity_type, "mw": entity.molecular_weight_da},
            )
            return entity

    def get_sequence(self, entity_id: str) -> Optional[SequenceEntity]:
        """
        Retrieve sequence entity by ID.

        Parameter entity_id (str): Sequence entity ID.
        Return Type: Optional[SequenceEntity]
        """
        with self._lock:
            return self._registry.get(entity_id)

    def list_sequences(self, entity_type: Optional[str] = None) -> List[SequenceEntity]:
        """
        List all registered sequences, optionally filtered by type.

        Parameter entity_type (Optional[str]): Filter by 'primer', 'plasmid', 'aptamer', 'protein_construct'.
        Return Type: List[SequenceEntity]
        """
        with self._lock:
            seqs = list(self._registry.values())
            if entity_type:
                seqs = [s for s in seqs if s.entity_type == entity_type]
            return seqs

    def clear_for_testing(self) -> None:
        """
        Reset internal sequence registry. For unit testing harness use only.

        """
        with self._lock:
            self._registry.clear()
            self._seed_standard_constructs()


_global_sequence_service = SequenceService()


def get_sequence_service() -> SequenceService:
    """
    Get the process-level singleton instance of SequenceService.

    Return Type: SequenceService
    """
    return _global_sequence_service
