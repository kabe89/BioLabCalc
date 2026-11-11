"""
Module: biolabcalc.eln.schema.models
Component: Declarative Data Models for ELN & LIMS Pipeline
Architectural Role: Complete schema models representing 21 core entities,
                    custom domain ENUMs, yield metrics, completion timestamps,
                    and bidirectional relationships with SQLite and PostgreSQL compatibility.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Union

from biolabcalc.eln.schema.database import (
    BaseModel,
    Field,
    ModelRegistry,
    Relationship,
)


# ============================================================================
# Domain Enumerations
# ============================================================================

class UserRole(str, Enum):
    """
    User authorization and role classifications in laboratory workspace.

    """
    PRINCIPAL_INVESTIGATOR = "principal_investigator"
    ACTIVE_RESEARCHER = "active_researcher"
    ROTATION_STUDENT = "rotation_student"
    LAB_MANAGER = "lab_manager"
    ALUMNI = "alumni"
    GUEST = "guest"


class ExptStatus(str, Enum):
    """
    Lifecycle status tracking for experimental campaigns, assays, and entries.

    """
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"
    ON_HOLD = "on_hold"


class FileFormatCategory(str, Enum):
    """
    Instrument file format categories for raw and processed multi-modal data.

    """
    FPLC_RES = "fplc_res"
    NANODROP_CSV = "nanodrop_csv"
    GEL_IMAGE_PNG = "gel_image_png"
    GEL_IMAGE_TIFF = "gel_image_tiff"
    EPHYS_ABF = "ephys_abf"
    FASTA = "fasta"
    GENBANK = "genbank"
    PDF = "pdf"
    MARKDOWN = "markdown"
    JSON = "json"
    TABULAR_CSV = "tabular_csv"


class BiomoleculeType(str, Enum):
    """
    Biochemical taxonomy of target biomolecules and inventory samples.

    """
    PLASMID_DNA = "plasmid_dna"
    GENOMIC_DNA = "genomic_dna"
    MRNA = "mrna"
    SIRNA = "sirna"
    RECOMBINANT_PROTEIN = "recombinant_protein"
    ANTIBODY = "antibody"
    PEPTIDE = "peptide"
    CHEMICAL_REAGENT = "chemical_reagent"


class StorageNodeType(str, Enum):
    """
    Physical hierarchy classifications for laboratory storage locations.

    """
    FACILITY = "facility"
    ROOM = "room"
    FREEZER_MINUS80 = "freezer_minus80"
    FREEZER_MINUS20 = "freezer_minus20"
    FRIDGE_4C = "fridge_4c"
    LIQUID_NITROGEN = "liquid_nitrogen"
    SHELF = "shelf"
    RACK = "rack"
    BOX = "box"
    PLATE_96 = "plate_96"
    PLATE_384 = "plate_384"


# ============================================================================
# Field Definition Factories
# ============================================================================

def UUIDColumn(primary_key: bool = False, default_gen: bool = True) -> Field:
    """Generate a UUID column descriptor."""
    def _gen() -> str:
        return str(uuid.uuid4())
    return Field(
        data_type="TEXT",
        primary_key=primary_key,
        nullable=not primary_key,
        default=_gen if default_gen else None,
        unique=primary_key
    )


def StringColumn(
    nullable: bool = True,
    default: Any = None,
    unique: bool = False,
    foreign_key: Optional[str] = None
) -> Field:
    """Generate a string/text column descriptor."""
    return Field(
        data_type="TEXT",
        nullable=nullable,
        default=default,
        unique=unique,
        foreign_key=foreign_key
    )


def IntegerColumn(
    nullable: bool = True,
    default: Any = None,
    unique: bool = False,
    foreign_key: Optional[str] = None
) -> Field:
    """Generate an integer column descriptor."""
    return Field(
        data_type="INTEGER",
        nullable=nullable,
        default=default,
        unique=unique,
        foreign_key=foreign_key
    )


def FloatColumn(
    nullable: bool = True,
    default: Any = None
) -> Field:
    """Generate a floating-point real column descriptor."""
    return Field(
        data_type="REAL",
        nullable=nullable,
        default=default
    )


def BooleanColumn(
    nullable: bool = False,
    default: bool = False
) -> Field:
    """Generate a boolean column descriptor."""
    return Field(
        data_type="BOOLEAN",
        nullable=nullable,
        default=default
    )


def DateTimeColumn(
    nullable: bool = True,
    auto_now: bool = False
) -> Field:
    """Generate a timestamp column descriptor."""
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
    return Field(
        data_type="TEXT",
        nullable=nullable,
        default=_now if auto_now else None
    )


def JSONColumn(
    nullable: bool = True,
    default: Any = None
) -> Field:
    """Generate a JSON data column descriptor."""
    return Field(
        data_type="TEXT",
        nullable=nullable,
        default=default,
        is_json=True
    )


def VectorColumn(
    dimensions: int = 1536,
    nullable: bool = True
) -> Field:
    """Generate a vector embedding column descriptor."""
    return Field(
        data_type="TEXT",
        nullable=nullable,
        default=None,
        is_vector=True,
        description=f"Float vector with {dimensions} dimensions"
    )


# ============================================================================
# Declarative Model Definitions (21 Tables)
# ============================================================================

class User(BaseModel):
    """
    Lab user profile tracking researchers, principal investigators, and alumni.

    """
    __tablename__ = "users"

    id = UUIDColumn(primary_key=True)
    email = StringColumn(nullable=False, unique=True)
    full_name = StringColumn(nullable=False)
    role = StringColumn(nullable=False, default=UserRole.ACTIVE_RESEARCHER.value)
    department = StringColumn(nullable=True)
    is_active = BooleanColumn(nullable=False, default=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)
    updated_at = DateTimeColumn(nullable=False, auto_now=True)


class AuditLog(BaseModel):
    """
    Audit log recording data modifications, logins, and compliance actions.

    """
    __tablename__ = "audit_logs"

    id = UUIDColumn(primary_key=True)
    user_id = StringColumn(nullable=True, foreign_key="users.id")
    action = StringColumn(nullable=False)
    entity_type = StringColumn(nullable=False)
    entity_id = StringColumn(nullable=False)
    changes = JSONColumn(nullable=True)
    client_ip = StringColumn(nullable=True)
    timestamp = DateTimeColumn(nullable=False, auto_now=True)


class StorageBlob(BaseModel):
    """
    Storage metadata for raw chromatograms, gel images, and instrument outputs.

    """
    __tablename__ = "storage_blobs"

    id = UUIDColumn(primary_key=True)
    file_name = StringColumn(nullable=False)
    file_path = StringColumn(nullable=False)
    file_size_bytes = IntegerColumn(nullable=False, default=0)
    file_hash_sha256 = StringColumn(nullable=False)
    format_category = StringColumn(nullable=False, default=FileFormatCategory.TABULAR_CSV.value)
    mime_type = StringColumn(nullable=False)
    uploaded_by = StringColumn(nullable=True, foreign_key="users.id")
    created_at = DateTimeColumn(nullable=False, auto_now=True)


class SopTemplate(BaseModel):
    """
    Standard Operating Procedure (SOP) versioned markdown documentation template.

    """
    __tablename__ = "sop_templates"

    id = UUIDColumn(primary_key=True)
    title = StringColumn(nullable=False)
    code = StringColumn(nullable=False, unique=True)
    version = StringColumn(nullable=False, default="1.0")
    category = StringColumn(nullable=False)
    content_markdown = StringColumn(nullable=False)
    created_by = StringColumn(nullable=True, foreign_key="users.id")
    created_at = DateTimeColumn(nullable=False, auto_now=True)
    updated_at = DateTimeColumn(nullable=False, auto_now=True)


class ExperimentalCampaign(BaseModel):
    """
    Top-level experimental campaign tracking objectives, overall yield metrics,
    and completion status across multi-day protocols.

    """
    __tablename__ = "experimental_campaigns"

    id = UUIDColumn(primary_key=True)
    title = StringColumn(nullable=False)
    slug = StringColumn(nullable=False, unique=True)
    objective = StringColumn(nullable=False)
    status = StringColumn(nullable=False, default=ExptStatus.PLANNED.value)
    lead_user_id = StringColumn(nullable=True, foreign_key="users.id")
    sop_id = StringColumn(nullable=True, foreign_key="sop_templates.id")
    started_at = DateTimeColumn(nullable=True)
    completed_at = DateTimeColumn(nullable=True)
    yield_mg_total = FloatColumn(nullable=True)
    yield_percent_recovery = FloatColumn(nullable=True)
    yield_mg_per_liter_culture = FloatColumn(nullable=True)
    yield_ug_plasmid = FloatColumn(nullable=True)
    yield_calculation_method = StringColumn(nullable=True)
    metadata_json = JSONColumn(nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)
    updated_at = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def daily_entries(self) -> List[NotebookDailyEntry]:
        """Fetch daily entries associated with campaign."""
        if getattr(self, "_cached_daily_entries", None) is not None:
            return self._cached_daily_entries
        if self._session and self.id:
            entries = self._session.query(NotebookDailyEntry).filter_by(campaign_id=self.id).order_by("day_number ASC").all()
            return entries
        return []

    @daily_entries.setter
    def daily_entries(self, val: Sequence[NotebookDailyEntry]) -> None:
        self._cached_daily_entries = list(val)

    @property
    def lead_user(self) -> Optional[User]:
        """Fetch lead researcher profile."""
        if getattr(self, "_cached_lead_user", None) is not None:
            return self._cached_lead_user
        if self._session and self.lead_user_id:
            return self._session.query(User).filter_by(id=self.lead_user_id).first()
        return None

    @lead_user.setter
    def lead_user(self, val: Optional[User]) -> None:
        self._cached_lead_user = val
        if val:
            self.lead_user_id = val.id

    @property
    def sop(self) -> Optional[SopTemplate]:
        """Fetch associated SOP."""
        if getattr(self, "_cached_sop", None) is not None:
            return self._cached_sop
        if self._session and self.sop_id:
            return self._session.query(SopTemplate).filter_by(id=self.sop_id).first()
        return None

    @sop.setter
    def sop(self, val: Optional[SopTemplate]) -> None:
        self._cached_sop = val
        if val:
            self.sop_id = val.id


class NotebookDailyEntry(BaseModel):
    """
    Daily bench notebook log tracking day-by-day operations, deviations, and yields.

    """
    __tablename__ = "notebook_daily_entries"

    id = UUIDColumn(primary_key=True)
    campaign_id = StringColumn(nullable=False, foreign_key="experimental_campaigns.id")
    day_number = IntegerColumn(nullable=False, default=0)
    entry_date = StringColumn(nullable=False)
    title = StringColumn(nullable=False)
    summary = StringColumn(nullable=False)
    protocol_deviations = StringColumn(nullable=True)
    status = StringColumn(nullable=False, default=ExptStatus.COMPLETED.value)
    completed_at = DateTimeColumn(nullable=True)
    yield_mg_total = FloatColumn(nullable=True)
    yield_percent_recovery = FloatColumn(nullable=True)
    yield_mg_per_liter_culture = FloatColumn(nullable=True)
    yield_ug_plasmid = FloatColumn(nullable=True)
    yield_calculation_method = StringColumn(nullable=True)
    operator_id = StringColumn(nullable=True, foreign_key="users.id")
    created_at = DateTimeColumn(nullable=False, auto_now=True)
    updated_at = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def campaign(self) -> Optional[ExperimentalCampaign]:
        """Fetch parent experimental campaign."""
        if getattr(self, "_cached_campaign", None) is not None:
            return self._cached_campaign
        if self._session and self.campaign_id:
            return self._session.query(ExperimentalCampaign).filter_by(id=self.campaign_id).first()
        return None

    @campaign.setter
    def campaign(self, val: Optional[ExperimentalCampaign]) -> None:
        self._cached_campaign = val
        if val:
            self.campaign_id = val.id

    @property
    def timepoints(self) -> List[NotebookTimepointLog]:
        """Fetch timepoints logged during this entry."""
        if getattr(self, "_cached_timepoints", None) is not None:
            return self._cached_timepoints
        if self._session and self.id:
            return self._session.query(NotebookTimepointLog).filter_by(entry_id=self.id).order_by("elapsed_minutes ASC").all()
        return []

    @timepoints.setter
    def timepoints(self, val: Sequence[NotebookTimepointLog]) -> None:
        self._cached_timepoints = list(val)

    @property
    def operator(self) -> Optional[User]:
        """Fetch operator user profile."""
        if getattr(self, "_cached_operator", None) is not None:
            return self._cached_operator
        if self._session and self.operator_id:
            return self._session.query(User).filter_by(id=self.operator_id).first()
        return None

    @operator.setter
    def operator(self, val: Optional[User]) -> None:
        self._cached_operator = val
        if val:
            self.operator_id = val.id


class NotebookTimepointLog(BaseModel):
    """
    Kinetic timepoint monitoring (OD600, temperature, RPM) during bacterial growth.

    """
    __tablename__ = "notebook_timepoint_logs"

    id = UUIDColumn(primary_key=True)
    entry_id = StringColumn(nullable=False, foreign_key="notebook_daily_entries.id")
    timepoint_label = StringColumn(nullable=False)
    elapsed_minutes = IntegerColumn(nullable=False, default=0)
    temperature_c = FloatColumn(nullable=True)
    od600 = FloatColumn(nullable=True)
    rpm = IntegerColumn(nullable=True)
    parameters_json = JSONColumn(nullable=True)
    notes = StringColumn(nullable=True)
    timestamp = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def entry(self) -> Optional[NotebookDailyEntry]:
        """Fetch parent daily entry."""
        if getattr(self, "_cached_entry", None) is not None:
            return self._cached_entry
        if self._session and self.entry_id:
            return self._session.query(NotebookDailyEntry).filter_by(id=self.entry_id).first()
        return None

    @entry.setter
    def entry(self, val: Optional[NotebookDailyEntry]) -> None:
        self._cached_entry = val
        if val:
            self.entry_id = val.id


class BioSequence(BaseModel):
    """
    Biomolecular sequence data, biophysical properties, and plasmid annotations.

    """
    __tablename__ = "bio_sequences"

    id = UUIDColumn(primary_key=True)
    name = StringColumn(nullable=False)
    biomolecule_type = StringColumn(nullable=False, default=BiomoleculeType.RECOMBINANT_PROTEIN.value)
    sequence_data = StringColumn(nullable=False)
    length_bp_or_aa = IntegerColumn(nullable=False)
    molecular_weight_da = FloatColumn(nullable=True)
    isoelectric_point_pi = FloatColumn(nullable=True)
    extinction_coefficient_e280 = FloatColumn(nullable=True)
    plasmid_map_json = JSONColumn(nullable=True)
    created_by = StringColumn(nullable=True, foreign_key="users.id")
    created_at = DateTimeColumn(nullable=False, auto_now=True)


class PcrAssay(BaseModel):
    """
    Polymerase chain reaction assay execution record and primer configuration.

    """
    __tablename__ = "pcr_assays"

    id = UUIDColumn(primary_key=True)
    campaign_id = StringColumn(nullable=True, foreign_key="experimental_campaigns.id")
    daily_entry_id = StringColumn(nullable=True, foreign_key="notebook_daily_entries.id")
    target_gene = StringColumn(nullable=False)
    forward_primer_name = StringColumn(nullable=False)
    forward_primer_seq = StringColumn(nullable=False)
    reverse_primer_name = StringColumn(nullable=False)
    reverse_primer_seq = StringColumn(nullable=False)
    annealing_temp_c = FloatColumn(nullable=False)
    extension_time_sec = IntegerColumn(nullable=False)
    cycle_count = IntegerColumn(nullable=False, default=30)
    status = StringColumn(nullable=False, default=ExptStatus.COMPLETED.value)
    completed_at = DateTimeColumn(nullable=True)
    yield_mg_total = FloatColumn(nullable=True)
    yield_percent_recovery = FloatColumn(nullable=True)
    yield_mg_per_liter_culture = FloatColumn(nullable=True)
    yield_ug_plasmid = FloatColumn(nullable=True)
    yield_calculation_method = StringColumn(nullable=True)
    notes = StringColumn(nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)


class NanodropMeasurement(BaseModel):
    """
    Spectrophotometric quantification record (A260, A280, concentration, purity ratios).

    """
    __tablename__ = "nanodrop_measurements"

    id = UUIDColumn(primary_key=True)
    campaign_id = StringColumn(nullable=True, foreign_key="experimental_campaigns.id")
    daily_entry_id = StringColumn(nullable=True, foreign_key="notebook_daily_entries.id")
    sample_name = StringColumn(nullable=False)
    biomolecule_type = StringColumn(nullable=False, default=BiomoleculeType.RECOMBINANT_PROTEIN.value)
    concentration_mg_per_ml = FloatColumn(nullable=False)
    a280 = FloatColumn(nullable=False)
    a260 = FloatColumn(nullable=False)
    a260_a280_ratio = FloatColumn(nullable=False)
    a260_a230_ratio = FloatColumn(nullable=True)
    buffer_blank = StringColumn(nullable=False)
    status = StringColumn(nullable=False, default=ExptStatus.COMPLETED.value)
    completed_at = DateTimeColumn(nullable=True)
    yield_mg_total = FloatColumn(nullable=True)
    yield_percent_recovery = FloatColumn(nullable=True)
    yield_mg_per_liter_culture = FloatColumn(nullable=True)
    yield_ug_plasmid = FloatColumn(nullable=True)
    yield_calculation_method = StringColumn(nullable=True)
    raw_blob_id = StringColumn(nullable=True, foreign_key="storage_blobs.id")
    created_at = DateTimeColumn(nullable=False, auto_now=True)


class FplcColumn(BaseModel):
    """
    Chromatography column asset tracking bed volume, pressure limits, and operational status.

    """
    __tablename__ = "fplc_columns"

    id = UUIDColumn(primary_key=True)
    name = StringColumn(nullable=False)
    column_type = StringColumn(nullable=False)
    bed_volume_ml = FloatColumn(nullable=False)
    max_pressure_mpa = FloatColumn(nullable=False)
    recommended_flow_rate_ml_min = FloatColumn(nullable=False)
    serial_number = StringColumn(nullable=True)
    current_status = StringColumn(nullable=False, default="operational")
    created_at = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def runs(self) -> List[FplcRun]:
        """Fetch all FPLC runs executed on column."""
        if getattr(self, "_cached_runs", None) is not None:
            return self._cached_runs
        if self._session and self.id:
            return self._session.query(FplcRun).filter_by(column_id=self.id).all()
        return []

    @runs.setter
    def runs(self, val: Sequence[FplcRun]) -> None:
        self._cached_runs = list(val)


class FplcRun(BaseModel):
    """
    FPLC chromatography run record tracking buffer profiles, flow rates, and yield metrics.

    """
    __tablename__ = "fplc_runs"

    id = UUIDColumn(primary_key=True)
    campaign_id = StringColumn(nullable=True, foreign_key="experimental_campaigns.id")
    daily_entry_id = StringColumn(nullable=True, foreign_key="notebook_daily_entries.id")
    column_id = StringColumn(nullable=True, foreign_key="fplc_columns.id")
    run_name = StringColumn(nullable=False)
    purification_step = StringColumn(nullable=False)
    flow_rate_ml_min = FloatColumn(nullable=False)
    buffer_a = StringColumn(nullable=False)
    buffer_b = StringColumn(nullable=True)
    gradient_profile_json = JSONColumn(nullable=True)
    status = StringColumn(nullable=False, default=ExptStatus.COMPLETED.value)
    completed_at = DateTimeColumn(nullable=True)
    yield_mg_total = FloatColumn(nullable=True)
    yield_percent_recovery = FloatColumn(nullable=True)
    yield_mg_per_liter_culture = FloatColumn(nullable=True)
    yield_ug_plasmid = FloatColumn(nullable=True)
    yield_calculation_method = StringColumn(nullable=True)
    raw_data_blob_id = StringColumn(nullable=True, foreign_key="storage_blobs.id")
    chromatogram_summary_json = JSONColumn(nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def column(self) -> Optional[FplcColumn]:
        """Fetch column used in this run."""
        if getattr(self, "_cached_column", None) is not None:
            return self._cached_column
        if self._session and self.column_id:
            return self._session.query(FplcColumn).filter_by(id=self.column_id).first()
        return None

    @column.setter
    def column(self, val: Optional[FplcColumn]) -> None:
        self._cached_column = val
        if val:
            self.column_id = val.id

    @property
    def fractions(self) -> List[FplcFraction]:
        """Fetch collected fractions."""
        if getattr(self, "_cached_fractions", None) is not None:
            return self._cached_fractions
        if self._session and self.id:
            return self._session.query(FplcFraction).filter_by(run_id=self.id).order_by("retention_volume_ml ASC").all()
        return []

    @fractions.setter
    def fractions(self, val: Sequence[FplcFraction]) -> None:
        self._cached_fractions = list(val)


class FplcFraction(BaseModel):
    """
    Chromatography fraction collected during an FPLC purification run.

    """
    __tablename__ = "fplc_fractions"

    id = UUIDColumn(primary_key=True)
    run_id = StringColumn(nullable=False, foreign_key="fplc_runs.id")
    fraction_number = StringColumn(nullable=False)
    retention_volume_ml = FloatColumn(nullable=False)
    uv280_mau = FloatColumn(nullable=False)
    uv260_mau = FloatColumn(nullable=True)
    conductivity_ms_cm = FloatColumn(nullable=True)
    is_pooled = BooleanColumn(nullable=False, default=False)
    notes = StringColumn(nullable=True)

    @property
    def run(self) -> Optional[FplcRun]:
        """Fetch parent FPLC run."""
        if getattr(self, "_cached_run", None) is not None:
            return self._cached_run
        if self._session and self.run_id:
            return self._session.query(FplcRun).filter_by(id=self.run_id).first()
        return None

    @run.setter
    def run(self, val: Optional[FplcRun]) -> None:
        self._cached_run = val
        if val:
            self.run_id = val.id


class GelRecord(BaseModel):
    """
    Electrophoresis gel record (SDS-PAGE or agarose) with voltage, run time, and purity.

    """
    __tablename__ = "gel_records"

    id = UUIDColumn(primary_key=True)
    campaign_id = StringColumn(nullable=True, foreign_key="experimental_campaigns.id")
    daily_entry_id = StringColumn(nullable=True, foreign_key="notebook_daily_entries.id")
    gel_type = StringColumn(nullable=False)
    voltage_v = IntegerColumn(nullable=False)
    run_time_minutes = IntegerColumn(nullable=False)
    staining_method = StringColumn(nullable=False)
    status = StringColumn(nullable=False, default=ExptStatus.COMPLETED.value)
    completed_at = DateTimeColumn(nullable=True)
    image_blob_id = StringColumn(nullable=True, foreign_key="storage_blobs.id")
    purity_assessment_percent = FloatColumn(nullable=True)
    notes = StringColumn(nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def lanes(self) -> List[GelLane]:
        """Fetch lanes belonging to gel."""
        if getattr(self, "_cached_lanes", None) is not None:
            return self._cached_lanes
        if self._session and self.id:
            return self._session.query(GelLane).filter_by(gel_id=self.id).order_by("lane_number ASC").all()
        return []

    @lanes.setter
    def lanes(self, val: Sequence[GelLane]) -> None:
        self._cached_lanes = list(val)


class GelLane(BaseModel):
    """
    Single lane within an electrophoresis gel containing sample identity and band analysis.

    """
    __tablename__ = "gel_lanes"

    id = UUIDColumn(primary_key=True)
    gel_id = StringColumn(nullable=False, foreign_key="gel_records.id")
    lane_number = IntegerColumn(nullable=False)
    sample_name = StringColumn(nullable=False)
    sample_type = StringColumn(nullable=False)
    volume_loaded_ul = FloatColumn(nullable=False)
    estimated_mw_kda = FloatColumn(nullable=True)
    estimated_mass_ng = FloatColumn(nullable=True)
    purity_percentage = FloatColumn(nullable=True)
    band_analysis_json = JSONColumn(nullable=True)
    notes = StringColumn(nullable=True)

    @property
    def gel(self) -> Optional[GelRecord]:
        """Fetch parent gel record."""
        if getattr(self, "_cached_gel", None) is not None:
            return self._cached_gel
        if self._session and self.gel_id:
            return self._session.query(GelRecord).filter_by(id=self.gel_id).first()
        return None

    @gel.setter
    def gel(self, val: Optional[GelRecord]) -> None:
        self._cached_gel = val
        if val:
            self.gel_id = val.id


class EphysRecording(BaseModel):
    """
    Electrophysiology patch-clamp recording assay record and summary metrics.

    """
    __tablename__ = "ephys_recordings"

    id = UUIDColumn(primary_key=True)
    campaign_id = StringColumn(nullable=True, foreign_key="experimental_campaigns.id")
    cell_type = StringColumn(nullable=False)
    patch_configuration = StringColumn(nullable=False)
    bath_solution = StringColumn(nullable=False)
    pipette_solution = StringColumn(nullable=False)
    holding_potential_mv = FloatColumn(nullable=False)
    sampling_rate_khz = FloatColumn(nullable=False)
    raw_data_blob_id = StringColumn(nullable=True, foreign_key="storage_blobs.id")
    status = StringColumn(nullable=False, default=ExptStatus.COMPLETED.value)
    completed_at = DateTimeColumn(nullable=True)
    summary_metrics_json = JSONColumn(nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)


class CodeAnalysisRun(BaseModel):
    """
    Computational pipeline and script execution tracking for bioinformatic analysis.

    """
    __tablename__ = "code_analysis_runs"

    id = UUIDColumn(primary_key=True)
    campaign_id = StringColumn(nullable=True, foreign_key="experimental_campaigns.id")
    tool_name = StringColumn(nullable=False)
    script_path = StringColumn(nullable=False)
    git_commit_hash = StringColumn(nullable=True)
    parameters_json = JSONColumn(nullable=True)
    results_json = JSONColumn(nullable=True)
    status = StringColumn(nullable=False, default=ExptStatus.COMPLETED.value)
    completed_at = DateTimeColumn(nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)


class StorageHierarchyNode(BaseModel):
    """
    Recursive physical storage hierarchy node (Facility -> Room -> Freezer -> Rack).

    """
    __tablename__ = "storage_hierarchy_nodes"

    id = UUIDColumn(primary_key=True)
    parent_id = StringColumn(nullable=True, foreign_key="storage_hierarchy_nodes.id")
    name = StringColumn(nullable=False)
    node_type = StringColumn(nullable=False, default=StorageNodeType.FREEZER_MINUS80.value)
    temperature_c = FloatColumn(nullable=True)
    barcode = StringColumn(nullable=True, unique=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def parent(self) -> Optional[StorageHierarchyNode]:
        """Fetch parent storage node."""
        if getattr(self, "_cached_parent", None) is not None:
            return self._cached_parent
        if self._session and self.parent_id:
            return self._session.query(StorageHierarchyNode).filter_by(id=self.parent_id).first()
        return None

    @parent.setter
    def parent(self, val: Optional[StorageHierarchyNode]) -> None:
        self._cached_parent = val
        if val:
            self.parent_id = val.id

    @property
    def children(self) -> List[StorageHierarchyNode]:
        """Fetch child storage hierarchy nodes."""
        if getattr(self, "_cached_children", None) is not None:
            return self._cached_children
        if self._session and self.id:
            return self._session.query(StorageHierarchyNode).filter_by(parent_id=self.id).all()
        return []

    @children.setter
    def children(self, val: Sequence[StorageHierarchyNode]) -> None:
        self._cached_children = list(val)

    @property
    def freezer_boxes(self) -> List[FreezerBox]:
        """Fetch freezer boxes stored inside this node."""
        if getattr(self, "_cached_freezer_boxes", None) is not None:
            return self._cached_freezer_boxes
        if self._session and self.id:
            return self._session.query(FreezerBox).filter_by(hierarchy_node_id=self.id).all()
        return []

    @freezer_boxes.setter
    def freezer_boxes(self, val: Sequence[FreezerBox]) -> None:
        self._cached_freezer_boxes = list(val)


class FreezerBox(BaseModel):
    """
    Freezer box container tracking 2D coordinate grid and temperature specifications.

    """
    __tablename__ = "freezer_boxes"

    id = UUIDColumn(primary_key=True)
    hierarchy_node_id = StringColumn(nullable=True, foreign_key="storage_hierarchy_nodes.id")
    name = StringColumn(nullable=False)
    barcode = StringColumn(nullable=False, unique=True)
    row_count = IntegerColumn(nullable=False, default=9)
    col_count = IntegerColumn(nullable=False, default=9)
    temperature_c = FloatColumn(nullable=False, default=-80.0)
    notes = StringColumn(nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def hierarchy_node(self) -> Optional[StorageHierarchyNode]:
        """Fetch parent rack/freezer node."""
        if getattr(self, "_cached_hierarchy_node", None) is not None:
            return self._cached_hierarchy_node
        if self._session and self.hierarchy_node_id:
            return self._session.query(StorageHierarchyNode).filter_by(id=self.hierarchy_node_id).first()
        return None

    @hierarchy_node.setter
    def hierarchy_node(self, val: Optional[StorageHierarchyNode]) -> None:
        self._cached_hierarchy_node = val
        if val:
            self.hierarchy_node_id = val.id

    @property
    def tubes(self) -> List[InventoryTube]:
        """Fetch inventory sample tubes stored inside box."""
        if getattr(self, "_cached_tubes", None) is not None:
            return self._cached_tubes
        if self._session and self.id:
            return self._session.query(InventoryTube).filter_by(box_id=self.id).all()
        return []

    @tubes.setter
    def tubes(self, val: Sequence[InventoryTube]) -> None:
        self._cached_tubes = list(val)


class InventoryTube(BaseModel):
    """
    Physical sample tube placed in a freezer box with barcode, yield, and provenance.

    """
    __tablename__ = "inventory_tubes"

    id = UUIDColumn(primary_key=True)
    box_id = StringColumn(nullable=False, foreign_key="freezer_boxes.id")
    box_position = StringColumn(nullable=False)
    barcode = StringColumn(nullable=False, unique=True)
    sample_name = StringColumn(nullable=False)
    biomolecule_type = StringColumn(nullable=False, default=BiomoleculeType.RECOMBINANT_PROTEIN.value)
    concentration_mg_ml = FloatColumn(nullable=False)
    volume_ul = FloatColumn(nullable=False)
    buffer_composition = StringColumn(nullable=False)
    campaign_id = StringColumn(nullable=True, foreign_key="experimental_campaigns.id")
    status = StringColumn(nullable=False, default=ExptStatus.COMPLETED.value)
    completed_at = DateTimeColumn(nullable=True)
    yield_mg_total = FloatColumn(nullable=True)
    yield_percent_recovery = FloatColumn(nullable=True)
    yield_mg_per_liter_culture = FloatColumn(nullable=True)
    yield_ug_plasmid = FloatColumn(nullable=True)
    yield_calculation_method = StringColumn(nullable=True)
    metadata_json = JSONColumn(nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)

    @property
    def box(self) -> Optional[FreezerBox]:
        """Fetch parent freezer box."""
        if getattr(self, "_cached_box", None) is not None:
            return self._cached_box
        if self._session and self.box_id:
            return self._session.query(FreezerBox).filter_by(id=self.box_id).first()
        return None

    @box.setter
    def box(self, val: Optional[FreezerBox]) -> None:
        self._cached_box = val
        if val:
            self.box_id = val.id


class RagDocumentChunk(BaseModel):
    """
    Document chunk supporting dense vector embedding (1536-dim) and lexical search.

    """
    __tablename__ = "rag_document_chunks"

    id = UUIDColumn(primary_key=True)
    source_entity_type = StringColumn(nullable=False)
    source_entity_id = StringColumn(nullable=False)
    chunk_index = IntegerColumn(nullable=False, default=0)
    chunk_text = StringColumn(nullable=False)
    lexical_tsvector = StringColumn(nullable=True)
    extracted_metadata = JSONColumn(nullable=True)
    provenance_context = StringColumn(nullable=False)
    embedding = VectorColumn(dimensions=1536, nullable=True)
    created_at = DateTimeColumn(nullable=False, auto_now=True)


# Alias Base for SQLAlchemy compatibility
Base = BaseModel
