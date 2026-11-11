"""
Module: biolabcalc.eln.services.campaign_service
Component: Multi-Day Campaign Lifecycle, Daily Entries & Carry-Forward State Math Engine
Agent: @agent: eln-api-agent
Architectural Role: Core service governing experimental campaign lifecycle, daily lab notebook
entries, cross-day carry-forward mathematical modeling (e.g. harvest pellet weight to lysis buffer),
daily rollup aggregations, and standardized yield calculations.
"""

from __future__ import annotations

import math
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .audit_service import get_audit_service


@dataclass
class CampaignYields:
    """
    Standardized yield metrics recorded upon campaign culmination.

    Agent: @agent: eln-api-agent
    Architectural Role: Quantifies total, volumetric, recovery percentage, and plasmid yields.
    """

    yield_mg_total: Optional[float] = None
    yield_percent_recovery: Optional[float] = None
    yield_mg_per_liter_culture: Optional[float] = None
    yield_ug_plasmid: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize yields to dictionary.

        Agent: @agent: eln-api-agent
        Return Type: Dict[str, Any]
        """
        return asdict(self)


@dataclass
class DailyEntry:
    """
    Structured lab notebook record for a single day within an experimental campaign.

    Agent: @agent: eln-api-agent
    Architectural Role: Stores state inputs, experimental observations, timepoint references,
    SOP fork references, and state outputs carried forward into subsequent days.
    """

    entry_id: str
    campaign_id: str
    day_number: int
    date: str
    title: str
    sop_fork_id: Optional[str] = None
    state_inputs: Dict[str, Any] = field(default_factory=dict)
    state_outputs: Dict[str, Any] = field(default_factory=dict)
    timepoints: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    status: str = "draft"  # draft, in_progress, completed
    created_by: str = "unknown"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize daily notebook entry to dictionary.

        Agent: @agent: eln-api-agent
        Return Type: Dict[str, Any]
        """
        return asdict(self)


@dataclass
class Campaign:
    """
    Experimental campaign entity tracking multi-day protocols, construct targets, and yields.

    Agent: @agent: eln-api-agent
    Architectural Role: Aggregate root coordinating daily notebook entries, lifecycle state transitions,
    and culmination analytics.
    """

    campaign_id: str
    title: str
    description: str
    construct_id: str
    status: str  # planned, in_progress, completed, aborted
    created_by: str
    created_at: str
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    target_organism: str = "E. coli BL21(DE3)"
    daily_entries: List[DailyEntry] = field(default_factory=list)
    yields: CampaignYields = field(default_factory=CampaignYields)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize campaign to dictionary.

        Agent: @agent: eln-api-agent
        Return Type: Dict[str, Any]
        """
        return {
            "campaign_id": self.campaign_id,
            "title": self.title,
            "description": self.description,
            "construct_id": self.construct_id,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "start_date": self.start_date,
            "completion_date": self.completion_date,
            "target_organism": self.target_organism,
            "daily_entries": [e.to_dict() for e in self.daily_entries],
            "yields": self.yields.to_dict(),
        }


class CampaignService:
    """
    Core service managing campaign life cycles, daily entries, and carry-forward state math.

    Agent: @agent: eln-api-agent
    Architectural Role: Coordinates lifecycle state machines, validates cross-day dependencies,
    computes deterministic reagent formulations based on prior day outputs, and logs audit events.
    """

    def __init__(self) -> None:
        """
        Initialize CampaignService in-memory repository with thread synchronization.

        Agent: @agent: eln-api-agent
        """
        self._lock = threading.RLock()
        self._campaigns: Dict[str, Campaign] = {}
        self._audit_service = get_audit_service()

    def create_campaign(
        self,
        title: str,
        description: str,
        construct_id: str,
        created_by: str,
        target_organism: str = "E. coli BL21(DE3)",
        start_date: Optional[str] = None,
    ) -> Campaign:
        """
        Create and persist a new experimental campaign.

        Agent: @agent: eln-api-agent
        Parameter title (str): Short descriptive campaign name.
        Parameter description (str): Full objective and scientific rationale.
        Parameter construct_id (str): Identifier of targeted plasmid or construct (e.g. pET-28a-T7RNAP).
        Parameter created_by (str): Researcher username or identity.
        Parameter target_organism (str): Host strain or organism (default: E. coli BL21(DE3)).
        Parameter start_date (Optional[str]): Initialized start date.
        Return Type: Campaign
        """
        with self._lock:
            campaign_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()
            campaign = Campaign(
                campaign_id=campaign_id,
                title=title,
                description=description,
                construct_id=construct_id,
                status="planned",
                created_by=created_by,
                created_at=now_iso,
                start_date=start_date or now_iso[:10],
                target_organism=target_organism,
                daily_entries=[],
                yields=CampaignYields(),
            )
            self._campaigns[campaign_id] = campaign

            self._audit_service.record_event(
                entity_type="campaign",
                entity_id=campaign_id,
                action="CREATE",
                performed_by=created_by,
                previous_state=None,
                new_state=campaign.to_dict(),
                metadata={"title": title, "construct_id": construct_id},
            )
            return campaign

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """
        Retrieve campaign by unique identifier.

        Agent: @agent: eln-api-agent
        Parameter campaign_id (str): Unique campaign identifier.
        Return Type: Optional[Campaign]
        """
        with self._lock:
            return self._campaigns.get(campaign_id)

    def list_campaigns(self, status: Optional[str] = None) -> List[Campaign]:
        """
        List all registered campaigns, optionally filtered by lifecycle status.

        Agent: @agent: eln-api-agent
        Parameter status (Optional[str]): Status filter ('planned', 'in_progress', 'completed', 'aborted').
        Return Type: List[Campaign]
        """
        with self._lock:
            campaigns = list(self._campaigns.values())
            if status is not None:
                campaigns = [c for c in campaigns if c.status == status]
            return campaigns

    def add_daily_entry(
        self,
        campaign_id: str,
        day_number: int,
        title: str,
        created_by: str,
        date: Optional[str] = None,
        sop_fork_id: Optional[str] = None,
        state_inputs: Optional[Dict[str, Any]] = None,
        notes: str = "",
    ) -> DailyEntry:
        """
        Append a new daily notebook entry to an active campaign.

        Agent: @agent: eln-api-agent
        Parameter campaign_id (str): Target campaign ID.
        Parameter day_number (int): Ordinal day number (e.g. 1, 2, 3).
        Parameter title (str): Header title for day's workflow.
        Parameter created_by (str): Operator recording entry.
        Parameter date (Optional[str]): Calendar date (YYYY-MM-DD). Defaults to current UTC date.
        Parameter sop_fork_id (Optional[str]): Referenced instantiated SOP fork identifier.
        Parameter state_inputs (Optional[Dict[str, Any]]): Inherited or initial state parameters.
        Parameter notes (str): Daily notes and observations.
        Return Type: DailyEntry
        """
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if not campaign:
                raise KeyError(f"Campaign with ID '{campaign_id}' not found.")

            # Transition campaign to in_progress if still planned
            if campaign.status == "planned":
                campaign.status = "in_progress"

            entry_id = f"ENTRY-{campaign_id}-D{day_number}-{uuid.uuid4().hex[:4].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()
            entry = DailyEntry(
                entry_id=entry_id,
                campaign_id=campaign_id,
                day_number=day_number,
                date=date or now_iso[:10],
                title=title,
                sop_fork_id=sop_fork_id,
                state_inputs=state_inputs or {},
                state_outputs={},
                timepoints=[],
                notes=notes,
                status="in_progress",
                created_by=created_by,
                created_at=now_iso,
                updated_at=now_iso,
            )
            campaign.daily_entries.append(entry)

            self._audit_service.record_event(
                entity_type="daily_entry",
                entity_id=entry_id,
                action="CREATE",
                performed_by=created_by,
                previous_state=None,
                new_state=entry.to_dict(),
                metadata={"campaign_id": campaign_id, "day_number": day_number},
            )
            return entry

    def update_daily_entry(
        self,
        campaign_id: str,
        entry_id: str,
        updated_by: str,
        state_outputs: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        status: Optional[str] = None,
    ) -> DailyEntry:
        """
        Update state outputs, observations, or status of an existing daily entry.

        Agent: @agent: eln-api-agent
        Parameter campaign_id (str): Target campaign ID.
        Parameter entry_id (str): Daily entry ID.
        Parameter updated_by (str): User making modification.
        Parameter state_outputs (Optional[Dict[str, Any]]): Recorded experimental outputs.
        Parameter notes (Optional[str]): Appended or modified notes.
        Parameter status (Optional[str]): New entry status.
        Return Type: DailyEntry
        """
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if not campaign:
                raise KeyError(f"Campaign with ID '{campaign_id}' not found.")

            target_entry: Optional[DailyEntry] = None
            for entry in campaign.daily_entries:
                if entry.entry_id == entry_id:
                    target_entry = entry
                    break

            if not target_entry:
                raise KeyError(f"Daily entry '{entry_id}' not found in campaign '{campaign_id}'.")

            prev_state = target_entry.to_dict()
            now_iso = datetime.now(timezone.utc).isoformat()

            if state_outputs is not None:
                target_entry.state_outputs.update(state_outputs)
            if notes is not None:
                target_entry.notes = notes
            if status is not None:
                target_entry.status = status
            target_entry.updated_at = now_iso

            self._audit_service.record_event(
                entity_type="daily_entry",
                entity_id=entry_id,
                action="UPDATE",
                performed_by=updated_by,
                previous_state=prev_state,
                new_state=target_entry.to_dict(),
                metadata={"campaign_id": campaign_id},
            )
            return target_entry

    # -------------------------------------------------------------------------
    # CARRY-FORWARD STATE MATH (Exact Scientific Calculations)
    # -------------------------------------------------------------------------

    @staticmethod
    def calculate_harvest_to_lysis(
        pellet_weight_g: float,
        buffer_ratio_ml_per_g: float = 5.0,
        protease_tablet_per_ml: float = 50.0,
        lysozyme_mg_per_g: float = 0.2,
        dnase_u_per_g: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Calculate Day 3 lysis buffer, protease inhibitor, lysozyme, and DNase requirements
        directly from Day 2 harvest wet pellet weight.

        Agent: @agent: eln-api-agent
        Formula:
            lysis_buffer_volume_ml = pellet_weight_g * buffer_ratio_ml_per_g
            protease_tablets = ceil(lysis_buffer_volume_ml / protease_tablet_per_ml)
            lysozyme_mg = pellet_weight_g * lysozyme_mg_per_g
            dnase_i_units = pellet_weight_g * dnase_u_per_g
        Example:
            22.4 g pellet * 5.0 mL/g = 112.0 mL buffer.
            ceil(112.0 / 50.0) = 3 protease inhibitor tablets.

        Parameter pellet_weight_g (float): Harvest wet cell pellet weight in grams.
        Parameter buffer_ratio_ml_per_g (float): Buffer volume per gram pellet (default: 5.0 mL/g).
        Parameter protease_tablet_per_ml (float): Milliliters per protease inhibitor tablet (default: 50.0 mL).
        Parameter lysozyme_mg_per_g (float): Lysozyme dosage per gram pellet (default: 0.2 mg/g).
        Parameter dnase_u_per_g (float): DNase I units per gram pellet (default: 10.0 U/g).
        Return Type: Dict[str, Any]
        """
        if pellet_weight_g < 0:
            raise ValueError("Pellet weight cannot be negative.")

        lysis_buffer_volume_ml = round(pellet_weight_g * buffer_ratio_ml_per_g, 2)
        tablets = (
            math.ceil(lysis_buffer_volume_ml / protease_tablet_per_ml)
            if lysis_buffer_volume_ml > 0
            else 0
        )
        lysozyme_mg = round(pellet_weight_g * lysozyme_mg_per_g, 3)
        dnase_units = round(pellet_weight_g * dnase_u_per_g, 1)

        return {
            "pellet_weight_g": pellet_weight_g,
            "buffer_ratio_ml_per_g": buffer_ratio_ml_per_g,
            "lysis_buffer_volume_ml": lysis_buffer_volume_ml,
            "protease_inhibitor_tablets": tablets,
            "lysozyme_mg": lysozyme_mg,
            "dnase_i_units": dnase_units,
            "recommendation": (
                f"Resuspend {pellet_weight_g} g cell pellet in {lysis_buffer_volume_ml} mL lysis buffer "
                f"(ratio: {buffer_ratio_ml_per_g} mL/g). Add {tablets} protease inhibitor tablet(s), "
                f"{lysozyme_mg} mg lysozyme, and {dnase_units} U DNase I."
            ),
        }

    @staticmethod
    def calculate_culture_to_pellet(
        culture_volume_l: float,
        final_od600: float,
        wet_cell_weight_factor_g_per_od_l: float = 1.8,
    ) -> Dict[str, Any]:
        """
        Estimate wet cell pellet weight from culture volume and optical density OD600.

        Agent: @agent: eln-api-agent
        Parameter culture_volume_l (float): Total culture volume in liters.
        Parameter final_od600 (float): Measured absorbance at 600 nm at harvest.
        Parameter wet_cell_weight_factor_g_per_od_l (float): Grams wet cell per OD600 per liter (default: 1.8).
        Return Type: Dict[str, Any]
        """
        estimated_pellet_g = round(culture_volume_l * final_od600 * wet_cell_weight_factor_g_per_od_l, 2)
        return {
            "culture_volume_l": culture_volume_l,
            "final_od600": final_od600,
            "wet_cell_weight_factor": wet_cell_weight_factor_g_per_od_l,
            "estimated_pellet_weight_g": estimated_pellet_g,
        }

    @staticmethod
    def calculate_lysate_to_resin(
        lysate_volume_ml: float,
        estimated_target_conc_mg_ml: float = 1.5,
        resin_capacity_mg_per_ml: float = 40.0,
        safety_factor: float = 1.25,
    ) -> Dict[str, Any]:
        """
        Calculate required chromatography resin bed volume based on cleared lysate and estimated target protein.

        Agent: @agent: eln-api-agent
        Parameter lysate_volume_ml (float): Total volume of cleared soluble lysate in mL.
        Parameter estimated_target_conc_mg_ml (float): Estimated target protein concentration in lysate (mg/mL).
        Parameter resin_capacity_mg_per_ml (float): Dynamic binding capacity of resin (default: 40 mg/mL Ni-NTA).
        Parameter safety_factor (float): Multiplier ensuring excess binding capacity (default: 1.25).
        Return Type: Dict[str, Any]
        """
        total_target_protein_mg = round(lysate_volume_ml * estimated_target_conc_mg_ml, 2)
        resin_bed_volume_ml = round((total_target_protein_mg / resin_capacity_mg_per_ml) * safety_factor, 2)
        return {
            "lysate_volume_ml": lysate_volume_ml,
            "estimated_target_protein_mg": total_target_protein_mg,
            "resin_capacity_mg_per_ml": resin_capacity_mg_per_ml,
            "safety_factor": safety_factor,
            "recommended_resin_bed_volume_ml": max(1.0, resin_bed_volume_ml),
        }

    def carry_forward_harvest_to_lysis(
        self,
        campaign_id: str,
        harvest_day: int = 2,
        lysis_day: int = 3,
        buffer_ratio_ml_per_g: float = 5.0,
        user_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Execute carry-forward state math from harvest day (Day 2) output into lysis day (Day 3) input.

        Agent: @agent: eln-api-agent
        Takes the recorded harvest wet pellet weight (e.g. 22.4 g) from Day 2 state_outputs,
        computes the exact required lysis buffer volume (112.0 mL), updates Day 3 state_inputs,
        and logs the transaction in the immutable audit ledger.

        Parameter campaign_id (str): Target campaign ID.
        Parameter harvest_day (int): Day number of harvest (default: 2).
        Parameter lysis_day (int): Day number of lysis (default: 3).
        Parameter buffer_ratio_ml_per_g (float): Buffer ratio in mL per gram pellet (default: 5.0).
        Parameter user_id (str): User executing the state carry-forward.
        Return Type: Dict[str, Any]
        """
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if not campaign:
                raise KeyError(f"Campaign '{campaign_id}' not found.")

            harvest_entry = next((e for e in campaign.daily_entries if e.day_number == harvest_day), None)
            if not harvest_entry:
                raise ValueError(f"Harvest entry for Day {harvest_day} not found in campaign '{campaign_id}'.")

            pellet_weight = harvest_entry.state_outputs.get("harvest_pellet_weight_g") or harvest_entry.state_outputs.get("pellet_weight_g")
            if pellet_weight is None:
                raise ValueError(
                    f"Day {harvest_day} does not contain 'harvest_pellet_weight_g' or 'pellet_weight_g' in state_outputs."
                )

            math_result = self.calculate_harvest_to_lysis(
                pellet_weight_g=float(pellet_weight),
                buffer_ratio_ml_per_g=buffer_ratio_ml_per_g,
            )

            # Find or create lysis day entry
            lysis_entry = next((e for e in campaign.daily_entries if e.day_number == lysis_day), None)
            if not lysis_entry:
                # Auto-create Day 3 entry if not yet instantiated
                now_iso = datetime.now(timezone.utc).isoformat()
                lysis_entry = DailyEntry(
                    entry_id=f"ENTRY-{campaign_id}-D{lysis_day}-{uuid.uuid4().hex[:4].upper()}",
                    campaign_id=campaign_id,
                    day_number=lysis_day,
                    date=now_iso[:10],
                    title=f"Day {lysis_day}: Cell Lysis & Clarification",
                    state_inputs=math_result,
                    state_outputs={},
                    timepoints=[],
                    notes=f"Auto-initialized with carry-forward state from Day {harvest_day}.",
                    status="in_progress",
                    created_by=user_id,
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                campaign.daily_entries.append(lysis_entry)
            else:
                prev_state = lysis_entry.to_dict()
                lysis_entry.state_inputs.update(math_result)
                lysis_entry.updated_at = datetime.now(timezone.utc).isoformat()
                self._audit_service.record_event(
                    entity_type="daily_entry",
                    entity_id=lysis_entry.entry_id,
                    action="CARRY_FORWARD",
                    performed_by=user_id,
                    previous_state=prev_state,
                    new_state=lysis_entry.to_dict(),
                    metadata={
                        "campaign_id": campaign_id,
                        "source_day": harvest_day,
                        "target_day": lysis_day,
                        "pellet_weight_g": pellet_weight,
                        "lysis_buffer_volume_ml": math_result["lysis_buffer_volume_ml"],
                    },
                )

            return math_result

    # -------------------------------------------------------------------------
    # DAILY ROLLUP & CULMINATION YIELD ANALYTICS
    # -------------------------------------------------------------------------

    def generate_daily_rollup(self, campaign_id: str, day_number: int) -> Dict[str, Any]:
        """
        Aggregate and summarize all metrics, timepoints, outputs, and status for a campaign day.

        Agent: @agent: eln-api-agent
        Parameter campaign_id (str): Target campaign ID.
        Parameter day_number (int): Day number to summarize.
        Return Type: Dict[str, Any]
        """
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if not campaign:
                raise KeyError(f"Campaign '{campaign_id}' not found.")

            entry = next((e for e in campaign.daily_entries if e.day_number == day_number), None)
            if not entry:
                raise KeyError(f"No entry found for Day {day_number} in campaign '{campaign_id}'.")

            audit_trail = self._audit_service.get_trail(entity_type="daily_entry", entity_id=entry.entry_id)

            return {
                "campaign_id": campaign_id,
                "campaign_title": campaign.title,
                "construct_id": campaign.construct_id,
                "entry_id": entry.entry_id,
                "day_number": day_number,
                "date": entry.date,
                "title": entry.title,
                "status": entry.status,
                "sop_fork_id": entry.sop_fork_id,
                "state_inputs": entry.state_inputs,
                "state_outputs": entry.state_outputs,
                "timepoints_count": len(entry.timepoints),
                "timepoints": entry.timepoints,
                "notes": entry.notes,
                "audit_events_count": len(audit_trail),
                "last_updated": entry.updated_at,
            }

    def complete_campaign(
        self,
        campaign_id: str,
        user_id: str,
        yield_mg_total: float,
        culture_volume_l: float,
        theoretical_yield_mg: Optional[float] = None,
        yield_ug_plasmid: Optional[float] = None,
    ) -> Campaign:
        """
        Record final purification yields, calculate recovery benchmarks, and mark campaign completed.

        Agent: @agent: eln-api-agent
        Calculates:
            yield_mg_total = measured total protein yield in mg.
            yield_mg_per_liter_culture = yield_mg_total / culture_volume_l.
            yield_percent_recovery = (yield_mg_total / theoretical_yield_mg) * 100.0 (if provided).
            yield_ug_plasmid = plasmid yield if applicable.

        Parameter campaign_id (str): Target campaign ID.
        Parameter user_id (str): Approving operator/PI.
        Parameter yield_mg_total (float): Total mass of purified target protein in mg.
        Parameter culture_volume_l (float): Initial volume of culture in liters.
        Parameter theoretical_yield_mg (Optional[float]): Theoretical maximal yield in mg.
        Parameter yield_ug_plasmid (Optional[float]): Plasmid yield in micrograms.
        Return Type: Campaign
        """
        with self._lock:
            campaign = self._campaigns.get(campaign_id)
            if not campaign:
                raise KeyError(f"Campaign '{campaign_id}' not found.")

            if culture_volume_l <= 0:
                raise ValueError("Culture volume must be greater than zero.")

            mg_per_l = round(yield_mg_total / culture_volume_l, 2)
            recovery_pct = (
                round((yield_mg_total / theoretical_yield_mg) * 100.0, 2)
                if theoretical_yield_mg and theoretical_yield_mg > 0
                else None
            )

            prev_state = campaign.to_dict()
            now_iso = datetime.now(timezone.utc).isoformat()

            campaign.yields = CampaignYields(
                yield_mg_total=round(yield_mg_total, 3),
                yield_percent_recovery=recovery_pct,
                yield_mg_per_liter_culture=mg_per_l,
                yield_ug_plasmid=round(yield_ug_plasmid, 2) if yield_ug_plasmid is not None else None,
            )
            campaign.status = "completed"
            campaign.completion_date = now_iso

            self._audit_service.record_event(
                entity_type="campaign",
                entity_id=campaign_id,
                action="COMPLETE",
                performed_by=user_id,
                previous_state=prev_state,
                new_state=campaign.to_dict(),
                metadata={
                    "yield_mg_total": yield_mg_total,
                    "yield_mg_per_liter_culture": mg_per_l,
                    "yield_percent_recovery": recovery_pct,
                },
            )
            return campaign

    def clear_for_testing(self) -> None:
        """
        Reset internal campaign state. For unit testing harness use only.

        Agent: @agent: eln-api-agent
        """
        with self._lock:
            self._campaigns.clear()


_global_campaign_service = CampaignService()


def get_campaign_service() -> CampaignService:
    """
    Get the process-level singleton instance of CampaignService.

    Agent: @agent: eln-api-agent
    Return Type: CampaignService
    """
    return _global_campaign_service
