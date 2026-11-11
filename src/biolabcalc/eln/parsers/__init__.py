"""
Module: biolabcalc.eln.parsers
Component: Scientific Parsers and Multi-Modal Ingestion Package
Architectural Role: Core package exports for all laboratory instrument parsers
(Axon ABF/ATF, Cytiva ÄKTA UNICORN, Thermo NanoDrop, Bio-Rad Image Lab/TIFF,
Word/PDF document extractors) and Human-in-the-Loop (HITL) Vision-OCR engine.
"""

from biolabcalc.eln.parsers.abf_parser import (
    ABFData,
    ABFParser,
    ABFTag,
)
from biolabcalc.eln.parsers.biorad_parser import (
    BioRadImage,
    BioRadParser,
    ExposureMetadata,
)
from biolabcalc.eln.parsers.doc_parser import (
    DocParser,
    DocumentImage,
    DocumentParagraph,
    DocumentResult,
)
from biolabcalc.eln.parsers.fplc_parser import (
    BufferRecipe,
    ColumnMetadata,
    FPLCParser,
    FPLCResult,
    FractionEvent,
)
from biolabcalc.eln.parsers.nanodrop_parser import (
    NanoDropExperiment,
    NanoDropParser,
    NanoDropSample,
)
from biolabcalc.eln.parsers.ocr_engine import (
    OCREngine,
    OCRResult,
    OCRToken,
)

__all__ = [
    "ABFParser",
    "ABFData",
    "ABFTag",
    "FPLCParser",
    "FPLCResult",
    "FractionEvent",
    "ColumnMetadata",
    "BufferRecipe",
    "NanoDropParser",
    "NanoDropSample",
    "NanoDropExperiment",
    "BioRadParser",
    "BioRadImage",
    "ExposureMetadata",
    "DocParser",
    "DocumentResult",
    "DocumentParagraph",
    "DocumentImage",
    "OCREngine",
    "OCRToken",
    "OCRResult",
]
