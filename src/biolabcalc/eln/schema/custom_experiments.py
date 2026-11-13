"""
Module: biolabcalc.eln.schema.custom_experiments
Component: Dynamic No-Code Experiment Schema, Field Definitions & Pre-built Templates
Architectural Role: Core schema definitions for custom electronic lab notebook experiment
templates, structured sections, typed form fields with formula bindings, and experiment entries.
Supports serialization to/from JSON and YAML.
"""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class FieldDefinition:
    """
    Specification for an individual form or calculated field in a template.
    """

    id: str
    label: str
    type: str  # text, number, select, date, table, formula, textarea
    required: bool = False
    default: Any = None
    unit: Optional[str] = None
    options: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    formula: Optional[str] = None
    columns: Optional[List[Dict[str, Any]]] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert field definition to dictionary."""
        d: Dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "required": self.required,
        }
        if self.default is not None:
            d["default"] = self.default
        if self.unit is not None:
            d["unit"] = self.unit
        if self.options is not None:
            d["options"] = list(self.options)
        if self.min_value is not None:
            d["min_value"] = self.min_value
        if self.max_value is not None:
            d["max_value"] = self.max_value
        if self.formula is not None:
            d["formula"] = self.formula
        if self.columns is not None:
            d["columns"] = copy.deepcopy(self.columns)
        if self.description is not None:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FieldDefinition:
        """Construct FieldDefinition from dictionary."""
        return cls(
            id=str(data["id"]),
            label=str(data.get("label", data["id"])),
            type=str(data.get("type", "text")).lower(),
            required=bool(data.get("required", False)),
            default=data.get("default"),
            unit=data.get("unit"),
            options=list(data["options"]) if data.get("options") is not None else None,
            min_value=float(data["min_value"]) if data.get("min_value") is not None else None,
            max_value=float(data["max_value"]) if data.get("max_value") is not None else None,
            formula=data.get("formula"),
            columns=copy.deepcopy(data.get("columns")),
            description=data.get("description"),
        )


@dataclass
class SectionDefinition:
    """
    Logical grouping of related fields within an experiment template.
    """

    id: str
    title: str
    description: Optional[str] = None
    fields: List[FieldDefinition] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert section definition to dictionary."""
        res: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "fields": [f.to_dict() if isinstance(f, FieldDefinition) else f for f in self.fields],
        }
        if self.description is not None:
            res["description"] = self.description
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SectionDefinition:
        """Construct SectionDefinition from dictionary."""
        raw_fields = data.get("fields", [])
        parsed_fields = [
            f if isinstance(f, FieldDefinition) else FieldDefinition.from_dict(f)
            for f in raw_fields
        ]
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", data["id"])),
            description=data.get("description"),
            fields=parsed_fields,
        )


@dataclass
class CustomExperimentTemplate:
    """
    Template schema for custom, no-code lab experiment workflows.
    """

    id: str
    name: str
    category: str
    description: str
    version: str = "1.0.0"
    sections: List[SectionDefinition] = field(default_factory=list)
    created_by: str = "system"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_public: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "version": self.version,
            "sections": [
                s.to_dict() if isinstance(s, SectionDefinition) else s for s in self.sections
            ],
            "created_by": self.created_by,
            "created_at": self.created_at,
            "is_public": self.is_public,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CustomExperimentTemplate:
        """Construct CustomExperimentTemplate from dictionary."""
        raw_sections = data.get("sections", [])
        parsed_sections: List[SectionDefinition] = []
        for s in raw_sections:
            if isinstance(s, SectionDefinition):
                parsed_sections.append(s)
            elif isinstance(s, dict):
                parsed_sections.append(SectionDefinition.from_dict(s))

        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            category=str(data.get("category", "General")),
            description=str(data.get("description", "")),
            version=str(data.get("version", "1.0.0")),
            sections=parsed_sections,
            created_by=str(data.get("created_by", "system")),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
            is_public=bool(data.get("is_public", True)),
        )

    def to_yaml(self) -> str:
        """Serialize template to YAML string."""
        if HAS_YAML:
            return yaml.safe_dump(self.to_dict(), sort_keys=False, default_flow_style=False)
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> CustomExperimentTemplate:
        """Deserialize template from YAML string."""
        if HAS_YAML:
            data = yaml.safe_load(yaml_str)
        else:
            try:
                data = json.loads(yaml_str)
            except Exception:
                from biolabcalc.eln.config import parse_simple_yaml
                data = parse_simple_yaml(yaml_str)
        if not isinstance(data, dict):
            raise ValueError("YAML document must deserialize to a dictionary.")
        return cls.from_dict(data)


@dataclass
class CustomExperimentEntry:
    """
    Instantiated entry representing an executed custom experiment based on a template.
    """

    id: str
    template_id: str
    campaign_id: Optional[str]
    title: str
    form_data: Dict[str, Any] = field(default_factory=dict)
    calculated_values: Dict[str, Any] = field(default_factory=dict)
    status: str = "completed"
    approval_status: str = "pending"
    operator_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "id": self.id,
            "template_id": self.template_id,
            "campaign_id": self.campaign_id,
            "title": self.title,
            "form_data": copy.deepcopy(self.form_data),
            "calculated_values": copy.deepcopy(self.calculated_values),
            "status": self.status,
            "approval_status": self.approval_status,
            "operator_id": self.operator_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CustomExperimentEntry:
        """Construct CustomExperimentEntry from dictionary."""
        now_iso = datetime.now(timezone.utc).isoformat()
        return cls(
            id=str(data["id"]),
            template_id=str(data["template_id"]),
            campaign_id=data.get("campaign_id"),
            title=str(data.get("title", "Custom Experiment")),
            form_data=copy.deepcopy(data.get("form_data", {})),
            calculated_values=copy.deepcopy(data.get("calculated_values", {})),
            status=str(data.get("status", "completed")),
            approval_status=str(data.get("approval_status", "pending")),
            operator_id=data.get("operator_id"),
            created_at=str(data.get("created_at", now_iso)),
            updated_at=str(data.get("updated_at", now_iso)),
        )

    def to_yaml(self) -> str:
        """Serialize entry to YAML string."""
        if HAS_YAML:
            return yaml.safe_dump(self.to_dict(), sort_keys=False, default_flow_style=False)
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> CustomExperimentEntry:
        """Deserialize entry from YAML string."""
        if HAS_YAML:
            data = yaml.safe_load(yaml_str)
        else:
            try:
                data = json.loads(yaml_str)
            except Exception:
                from biolabcalc.eln.config import parse_simple_yaml
                data = parse_simple_yaml(yaml_str)
        if not isinstance(data, dict):
            raise ValueError("YAML document must deserialize to a dictionary.")
        return cls.from_dict(data)


# ============================================================================
# Pre-built Template Specifications
# ============================================================================

def get_prebuilt_templates() -> List[CustomExperimentTemplate]:
    """
    Instantiate and return the standard catalog of pre-built experiment templates.
    """
    templates: List[CustomExperimentTemplate] = []

    # 1. General Lab Notebook Entry
    t_general = CustomExperimentTemplate(
        id="tpl_general_notebook",
        name="General Lab Notebook Entry",
        category="General",
        description="Standard electronic lab notebook entry for recording daily protocols, hypotheses, materials, observations, and conclusions.",
        version="1.0.0",
        sections=[
            SectionDefinition(
                id="metadata",
                title="Experiment Metadata",
                description="General identification and calendar information.",
                fields=[
                    FieldDefinition(id="experiment_date", label="Experiment Date", type="date", required=True),
                    FieldDefinition(id="project_code", label="Project / Grant Code", type="text", required=False),
                    FieldDefinition(id="witness", label="Witness / Co-investigator", type="text", required=False),
                ],
            ),
            SectionDefinition(
                id="objectives",
                title="Objectives & Hypothesis",
                description="Core scientific goals and proposed hypotheses.",
                fields=[
                    FieldDefinition(id="objective", label="Experimental Objective", type="text", required=True),
                    FieldDefinition(id="hypothesis", label="Working Hypothesis", type="text", required=False),
                ],
            ),
            SectionDefinition(
                id="materials",
                title="Materials & Reagents",
                description="Consumables, buffers, and equipment tracking.",
                fields=[
                    FieldDefinition(id="reagents", label="Reagents & Lot Numbers", type="text", required=False),
                    FieldDefinition(id="equipment", label="Instruments & Equipment IDs", type="text", required=False),
                ],
            ),
            SectionDefinition(
                id="procedure",
                title="Protocol & Execution",
                description="Detailed procedural steps and deviations.",
                fields=[
                    FieldDefinition(id="protocol_steps", label="Procedure Steps & Observations", type="text", required=True),
                    FieldDefinition(id="deviations", label="Protocol Deviations", type="text", required=False),
                ],
            ),
            SectionDefinition(
                id="results",
                title="Results & Conclusions",
                description="Experimental findings and next steps.",
                fields=[
                    FieldDefinition(id="results_summary", label="Summary of Results", type="text", required=True),
                    FieldDefinition(id="conclusions", label="Conclusions & Follow-up Actions", type="text", required=False),
                ],
            ),
        ],
    )
    templates.append(t_general)

    # 2. Molecular Cloning & Assembly
    t_cloning = CustomExperimentTemplate(
        id="tpl_molecular_cloning",
        name="Molecular Cloning & Assembly",
        category="Molecular Biology",
        description="Template for plasmid vector construction, restriction/Gibson assembly, molar ratio stoichiometry, and colony screening.",
        version="1.0.0",
        sections=[
            SectionDefinition(
                id="construct_design",
                title="Construct Design",
                description="Vector and insert fragment dimensions.",
                fields=[
                    FieldDefinition(id="vector_name", label="Destination Vector Name", type="text", required=True),
                    FieldDefinition(id="vector_size_bp", label="Vector Size (bp)", type="number", required=True, min_value=100.0, unit="bp"),
                    FieldDefinition(id="insert_name", label="Insert / Gene Name", type="text", required=True),
                    FieldDefinition(id="insert_size_bp", label="Insert Size (bp)", type="number", required=True, min_value=10.0, unit="bp"),
                ],
            ),
            SectionDefinition(
                id="reaction_stoichiometry",
                title="Assembly Reaction & Stoichiometry",
                description="Stoichiometric mass calculations and reaction conditions.",
                fields=[
                    FieldDefinition(
                        id="assembly_method",
                        label="Assembly Method",
                        type="select",
                        required=True,
                        options=["Gibson Assembly", "Golden Gate Assembly", "Restriction-Ligation", "TOPO Cloning"],
                        default="Gibson Assembly",
                    ),
                    FieldDefinition(id="vector_mass_ng", label="Vector Mass (ng)", type="number", required=True, min_value=1.0, unit="ng"),
                    FieldDefinition(id="molar_ratio", label="Molar Ratio (Insert:Vector)", type="number", required=True, min_value=0.1, default=3.0),
                    FieldDefinition(
                        id="required_insert_ng",
                        label="Calculated Insert Mass (ng)",
                        type="formula",
                        unit="ng",
                        formula="(vector_mass_ng * (insert_size_bp / vector_size_bp)) * molar_ratio",
                    ),
                    FieldDefinition(id="reaction_volume_ul", label="Reaction Volume (µL)", type="number", required=True, min_value=5.0, default=20.0, unit="µL"),
                    FieldDefinition(id="incubation_temp_c", label="Incubation Temperature (°C)", type="number", required=True, min_value=0.0, max_value=100.0, default=50.0, unit="°C"),
                    FieldDefinition(id="incubation_time_min", label="Incubation Time (min)", type="number", required=True, min_value=1.0, default=60.0, unit="min"),
                ],
            ),
            SectionDefinition(
                id="transformation_screening",
                title="Transformation & Screening",
                description="Bacterial transformation, antibiotic selection, and colony yield.",
                fields=[
                    FieldDefinition(
                        id="competent_cells",
                        label="Competent Cell Strain",
                        type="select",
                        required=True,
                        options=["DH5alpha", "TOP10", "NEB Stable", "BL21(DE3)", "Stbl3"],
                        default="DH5alpha",
                    ),
                    FieldDefinition(
                        id="selection_antibiotic",
                        label="Selection Antibiotic",
                        type="select",
                        required=True,
                        options=["Ampicillin (100 ug/mL)", "Kanamycin (50 ug/mL)", "Chloramphenicol (34 ug/mL)", "Spectinomycin (100 ug/mL)", "Tetracycline (10 ug/mL)"],
                        default="Ampicillin (100 ug/mL)",
                    ),
                    FieldDefinition(id="colony_count", label="Colony Count", type="number", min_value=0.0, required=False),
                    FieldDefinition(id="positive_colonies", label="Verified Positive Colonies", type="number", min_value=0.0, required=False),
                ],
            ),
        ],
    )
    templates.append(t_cloning)

    # 3. Protein Expression & Purification
    t_protein = CustomExperimentTemplate(
        id="tpl_protein_expression",
        name="Protein Expression & Purification",
        category="Protein Biochemistry",
        description="Tracks recombinant protein expression, biomass yield, IMAC/SEC chromatography, A280 spectroscopy, and extinction-coefficient normalized metrics.",
        version="1.0.0",
        sections=[
            SectionDefinition(
                id="upstream_expression",
                title="Upstream Expression",
                description="Host strain, culture volume, induction conditions, and biomass.",
                fields=[
                    FieldDefinition(id="target_protein", label="Target Protein Name", type="text", required=True),
                    FieldDefinition(
                        id="expression_host",
                        label="Expression Host",
                        type="select",
                        required=True,
                        options=["E. coli BL21(DE3)", "E. coli Rosetta 2(DE3)", "E. coli Origami B", "Expi293F", "Sf9 Insect Cells"],
                        default="E. coli BL21(DE3)",
                    ),
                    FieldDefinition(id="culture_volume_l", label="Culture Volume (L)", type="number", required=True, min_value=0.01, unit="L"),
                    FieldDefinition(id="induction_od600", label="Induction OD600", type="number", required=True, min_value=0.1, max_value=30.0, unit="AU"),
                    FieldDefinition(id="iptg_concentration_mm", label="IPTG / Inducer (mM)", type="number", min_value=0.0, default=0.5, unit="mM"),
                    FieldDefinition(id="harvest_pellet_mass_g", label="Wet Cell Pellet Mass (g)", type="number", required=True, min_value=0.1, unit="g"),
                ],
            ),
            SectionDefinition(
                id="lysis_purification",
                title="Lysis & Chromatography",
                description="Cell disruption, column specifications, and elution volume.",
                fields=[
                    FieldDefinition(id="lysis_buffer_volume_ml", label="Lysis Buffer Volume (mL)", type="number", required=True, min_value=1.0, unit="mL"),
                    FieldDefinition(
                        id="column_type",
                        label="Chromatography Column",
                        type="select",
                        required=True,
                        options=["HisTrap FF 5mL", "HisTrap HP 1mL", "StrepTrap HP 5mL", "GSTrap 4B 5mL", "Superdex 200 Increase 10/300 GL"],
                        default="HisTrap FF 5mL",
                    ),
                    FieldDefinition(id="elution_volume_ml", label="Elution Volume (mL)", type="number", required=True, min_value=0.1, unit="mL"),
                ],
            ),
            SectionDefinition(
                id="quantification_yield",
                title="Quantification & Yield",
                description="Absorbance at 280 nm and computed protein yield metrics.",
                fields=[
                    FieldDefinition(id="absorbance_a280", label="Absorbance A280", type="number", required=True, min_value=0.0, unit="AU"),
                    FieldDefinition(id="extinction_coefficient", label="Extinction Coefficient", type="number", required=True, min_value=0.001, unit="AU/(mg/mL)"),
                    FieldDefinition(
                        id="protein_concentration_mg_ml",
                        label="Calculated Concentration (mg/mL)",
                        type="formula",
                        unit="mg/mL",
                        formula="absorbance_a280 / extinction_coefficient",
                    ),
                    FieldDefinition(
                        id="total_protein_mg",
                        label="Total Protein Yield (mg)",
                        type="formula",
                        unit="mg",
                        formula="(absorbance_a280 / extinction_coefficient) * elution_volume_ml",
                    ),
                    FieldDefinition(
                        id="specific_yield_mg_per_l",
                        label="Specific Yield (mg/L Culture)",
                        type="formula",
                        unit="mg/L",
                        formula="((absorbance_a280 / extinction_coefficient) * elution_volume_ml) / culture_volume_l",
                    ),
                ],
            ),
        ],
    )
    templates.append(t_protein)

    # 4. Cell Culture & Growth Kinetics
    t_cell = CustomExperimentTemplate(
        id="tpl_cell_culture",
        name="Cell Culture & Growth Kinetics",
        category="Cell Biology",
        description="Monitors mammalian or microbial cell passages, seeding densities, automated cell counts, and viability percentages.",
        version="1.0.0",
        sections=[
            SectionDefinition(
                id="cell_line_info",
                title="Cell Line & Passage Details",
                description="Cell line provenance, passage number, and vessel configuration.",
                fields=[
                    FieldDefinition(id="cell_line_name", label="Cell Line Name", type="text", required=True),
                    FieldDefinition(id="passage_number", label="Passage Number", type="number", required=True, min_value=0.0),
                    FieldDefinition(
                        id="culture_vessel",
                        label="Culture Vessel",
                        type="select",
                        required=True,
                        options=["T-25 Flask", "T-75 Flask", "T-175 Flask", "6-Well Plate", "10cm Dish", "Shake Flask 250mL", "Bioreactor"],
                        default="T-75 Flask",
                    ),
                    FieldDefinition(id="medium_type", label="Growth Medium", type="text", required=True),
                ],
            ),
            SectionDefinition(
                id="cell_counting",
                title="Cell Counting & Viability",
                description="Hemocytometer or automated cell counter counts and calculated viability.",
                fields=[
                    FieldDefinition(id="total_cells", label="Total Cell Count (cells)", type="number", required=True, min_value=1.0, unit="cells"),
                    FieldDefinition(id="viable_cells", label="Viable Cell Count (cells)", type="number", required=True, min_value=0.0, unit="cells"),
                    FieldDefinition(id="total_volume_ml", label="Resuspension Volume (mL)", type="number", required=True, min_value=0.1, unit="mL"),
                    FieldDefinition(
                        id="viability_percent",
                        label="Cell Viability (%)",
                        type="formula",
                        unit="%",
                        formula="(viable_cells / total_cells) * 100",
                    ),
                    FieldDefinition(
                        id="viable_cell_density",
                        label="Viable Cell Density (cells/mL)",
                        type="formula",
                        unit="cells/mL",
                        formula="viable_cells / total_volume_ml",
                    ),
                ],
            ),
            SectionDefinition(
                id="subculture_seeding",
                title="Subculture & Seeding",
                description="Subsequent seeding densities and incubator environmental conditions.",
                fields=[
                    FieldDefinition(id="target_seeding_density", label="Target Seeding Density (cells/mL)", type="number", min_value=100.0, unit="cells/mL"),
                    FieldDefinition(id="incubation_co2_pct", label="Incubator CO2 (%)", type="number", min_value=0.0, max_value=20.0, default=5.0, unit="%"),
                ],
            ),
        ],
    )
    templates.append(t_cell)

    # 5. Electrophysiology Patch-Clamp Recording
    t_ephys = CustomExperimentTemplate(
        id="tpl_electrophysiology",
        name="Electrophysiology Patch-Clamp Recording",
        category="Electrophysiology",
        description="Standard patch-clamp electrophysiology record: pipette and seal resistances, membrane capacitance, holding potentials, and current density normalization.",
        version="1.0.0",
        sections=[
            SectionDefinition(
                id="patch_configuration",
                title="Rig & Patch Configuration",
                description="Cell identifier, patch configuration, and pipette/bath solutions.",
                fields=[
                    FieldDefinition(id="cell_id", label="Cell / Sieve Identifier", type="text", required=True),
                    FieldDefinition(
                        id="recording_mode",
                        label="Recording Configuration",
                        type="select",
                        required=True,
                        options=["Whole-cell", "Perforated-patch", "Cell-attached", "Inside-out", "Outside-out"],
                        default="Whole-cell",
                    ),
                    FieldDefinition(id="internal_solution", label="Internal / Pipette Solution", type="text", required=True),
                    FieldDefinition(id="external_solution", label="External / Bath Solution", type="text", required=True),
                ],
            ),
            SectionDefinition(
                id="cell_parameters",
                title="Passive Membrane Properties",
                description="Electrode and cell electrical properties.",
                fields=[
                    FieldDefinition(id="pipette_resistance_mohm", label="Pipette Resistance (MΩ)", type="number", required=True, min_value=0.5, max_value=50.0, unit="MΩ"),
                    FieldDefinition(id="seal_resistance_gohm", label="Gigaseal Resistance (GΩ)", type="number", required=True, min_value=0.1, unit="GΩ"),
                    FieldDefinition(id="cell_capacitance_pf", label="Cell Capacitance (pF)", type="number", required=True, min_value=1.0, unit="pF"),
                    FieldDefinition(id="series_resistance_mohm", label="Series Resistance (MΩ)", type="number", min_value=0.1, unit="MΩ"),
                ],
            ),
            SectionDefinition(
                id="recording_kinetics",
                title="Current Measurements & Density",
                description="Voltage holding potential, measured peak currents, and normalized current density.",
                fields=[
                    FieldDefinition(id="holding_potential_mv", label="Holding Potential (mV)", type="number", required=True, default=-70.0, unit="mV"),
                    FieldDefinition(id="peak_inward_current_pa", label="Peak Inward Current (pA)", type="number", required=True, unit="pA"),
                    FieldDefinition(id="peak_outward_current_pa", label="Peak Outward Current (pA)", type="number", required=False, unit="pA"),
                    FieldDefinition(
                        id="current_density_pa_pf",
                        label="Current Density (pA/pF)",
                        type="formula",
                        unit="pA/pF",
                        formula="abs(peak_inward_current_pa) / cell_capacitance_pf",
                    ),
                ],
            ),
        ],
    )
    templates.append(t_ephys)

    # 6. Custom Blank Canvas
    t_blank = CustomExperimentTemplate(
        id="tpl_blank_canvas",
        name="Custom Blank Canvas",
        category="Custom",
        description="Unconstrained blank canvas experiment template for custom multi-step protocols, custom notes, data tables, and user-defined metrics.",
        version="1.0.0",
        sections=[
            SectionDefinition(
                id="overview",
                title="Experiment Overview",
                description="General experiment title and notes.",
                fields=[
                    FieldDefinition(id="experiment_title", label="Experiment Title", type="text", required=True),
                    FieldDefinition(id="summary_notes", label="Summary & Protocol Notes", type="text", required=False),
                ],
            ),
            SectionDefinition(
                id="data_table",
                title="Custom Measurements",
                description="Configurable tabular data entry.",
                fields=[
                    FieldDefinition(
                        id="measurements",
                        label="Measurement Table",
                        type="table",
                        required=False,
                        columns=[
                            {"key": "sample_id", "label": "Sample ID", "type": "text"},
                            {"key": "condition", "label": "Condition", "type": "text"},
                            {"key": "replicate", "label": "Replicate", "type": "number"},
                            {"key": "value", "label": "Measured Value", "type": "number"},
                            {"key": "notes", "label": "Notes", "type": "text"},
                        ],
                    ),
                ],
            ),
            SectionDefinition(
                id="conclusions",
                title="Conclusions",
                description="Observations and concluding remarks.",
                fields=[
                    FieldDefinition(id="final_remarks", label="Final Remarks", type="text", required=False),
                ],
            ),
        ],
    )
    templates.append(t_blank)

    return templates
