"""
Module: biolabcalc.eln.services.inventory_service
Component: Spatial Freezer Hierarchy, 2D Grid Occupancy & End-to-End Sample Lineage Engine
Agent: @agent: eln-api-agent
Architectural Role: Core service governing laboratory cold-chain spatial hierarchy
(Room -> Storage Unit -> Rack -> Box -> Tube Slot), 2D box grid slot occupancy management,
tube relocation with immutable audit logging, and graph-based upstream sample lineage resolution.
"""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .audit_service import get_audit_service
from .campaign_service import get_campaign_service
from .fplc_service import get_fplc_service
from .sequence_service import get_sequence_service


@dataclass
class Room:
    """
    Physical room or facility location.

    Agent: @agent: eln-api-agent
    Architectural Role: Top-level spatial boundary for storage units.
    """

    room_id: str
    name: str
    building: str
    floor: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize room to dictionary. Agent: @agent: eln-api-agent"""
        return asdict(self)


@dataclass
class StorageUnit:
    """
    Cold-chain temperature unit (-80C, -20C, 4C, LN2, ambient).

    Agent: @agent: eln-api-agent
    Architectural Role: Governs storage units housed within physical laboratory rooms.
    """

    unit_id: str
    room_id: str
    name: str
    unit_type: str  # -80C, -20C, 4C, LN2, ambient
    model_number: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize unit to dictionary. Agent: @agent: eln-api-agent"""
        return asdict(self)


@dataclass
class Rack:
    """
    Sub-compartment rack or shelf within a storage unit.

    Agent: @agent: eln-api-agent
    Architectural Role: Intermediate physical grouping holding multiple freezer storage boxes.
    """

    rack_id: str
    unit_id: str
    name: str
    shelf_level: int

    def to_dict(self) -> Dict[str, Any]:
        """Serialize rack to dictionary. Agent: @agent: eln-api-agent"""
        return asdict(self)


@dataclass
class Box:
    """
    2D coordinate cryogenic or storage box (9x9 or 10x10 grid).

    Agent: @agent: eln-api-agent
    Architectural Role: Defines 2D grid slot coordinate boundaries (e.g. A1 to I9).
    """

    box_id: str
    rack_id: str
    name: str
    box_type: str  # 9x9, 10x10
    row_count: int
    col_count: int
    temperature_target: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize box to dictionary. Agent: @agent: eln-api-agent"""
        return asdict(self)


@dataclass
class Tube:
    """
    Individual sample tube placed at a specific box grid slot.

    Agent: @agent: eln-api-agent
    Architectural Role: Sample entity recording lineage pointers, volume, concentration, and location.
    """

    tube_id: str
    barcode: str
    sample_name: str
    box_id: str
    slot: str  # e.g. 'A1', 'B4', 'I9'
    volume_ul: float
    concentration_mg_ml: Optional[float] = None
    construct_id: Optional[str] = None
    pool_id: Optional[str] = None
    daily_entry_id: Optional[str] = None
    campaign_id: Optional[str] = None
    nanodrop_id: Optional[str] = None
    notes: str = ""
    created_by: str = "unknown"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tube to dictionary. Agent: @agent: eln-api-agent"""
        return asdict(self)


class InventoryService:
    """
    Service managing multi-tier freezer spatial hierarchy, 2D box grid occupancy, and sample lineage.

    Agent: @agent: eln-api-agent
    Architectural Role: Orchestrates Room -> StorageUnit -> Rack -> Box -> Tube navigation,
    slot occupancy collision checks, audited tube movements, and graph-based lineage resolution.
    """

    def __init__(self) -> None:
        """
        Initialize inventory service repositories and seed baseline spatial infrastructure.

        Agent: @agent: eln-api-agent
        """
        self._lock = threading.RLock()
        self._rooms: Dict[str, Room] = {}
        self._units: Dict[str, StorageUnit] = {}
        self._racks: Dict[str, Rack] = {}
        self._boxes: Dict[str, Box] = {}
        self._tubes: Dict[str, Tube] = {}
        self._audit_service = get_audit_service()
        self._campaign_service = get_campaign_service()
        self._fplc_service = get_fplc_service()
        self._sequence_service = get_sequence_service()
        self._seed_standard_freezer_infrastructure()

    def _seed_standard_freezer_infrastructure(self) -> None:
        """
        Pre-seed baseline freezer spatial hierarchy: Room 402 -> -80C Freezer 1 -> Rack A -> Box-T7RNAP (9x9).

        Agent: @agent: eln-api-agent
        """
        room = Room(room_id="ROOM-402", name="Bioprocessing Suite 402", building="BioSciences South", floor="4")
        self._rooms[room.room_id] = room

        unit = StorageUnit(
            unit_id="UNIT-FREEZER-80-01",
            room_id=room.room_id,
            name="-80°C Ultra-Low Freezer #1",
            unit_type="-80C",
            model_number="Thermo Forma 88000",
        )
        self._units[unit.unit_id] = unit

        rack = Rack(rack_id="RACK-A", unit_id=unit.unit_id, name="Rack Alpha - Shelf 2", shelf_level=2)
        self._racks[rack.rack_id] = rack

        box = Box(
            box_id="BOX-T7RNAP-01",
            rack_id=rack.rack_id,
            name="Purified T7 RNA Polymerase Stocks",
            box_type="9x9",
            row_count=9,
            col_count=9,
            temperature_target="-80C",
        )
        self._boxes[box.box_id] = box

        # Seed initial tube
        now_iso = datetime.now(timezone.utc).isoformat()
        tube = Tube(
            tube_id="TUBE-T7RNAP-001",
            barcode="BC-T7-0001",
            sample_name="T7RNAP Fraction Pool Eluate",
            box_id=box.box_id,
            slot="A1",
            volume_ul=1000.0,
            concentration_mg_ml=2.85,
            construct_id="pET-28a-T7RNAP",
            pool_id="POOL-RUN-01-B4-B8",
            daily_entry_id="ENTRY-CMP-001-D3-0001",
            campaign_id="CMP-001",
            notes="Reference stock aliquot in 50% glycerol storage buffer.",
            created_by="pi_admin",
            created_at=now_iso,
            updated_at=now_iso,
        )
        self._tubes[tube.tube_id] = tube

    # -------------------------------------------------------------------------
    # SPATIAL HIERARCHY NAVIGATION
    # -------------------------------------------------------------------------

    def create_room(self, name: str, building: str, floor: str) -> Room:
        """Create a room. Agent: @agent: eln-api-agent"""
        with self._lock:
            room_id = f"ROOM-{uuid.uuid4().hex[:6].upper()}"
            room = Room(room_id=room_id, name=name, building=building, floor=floor)
            self._rooms[room_id] = room
            return room

    def create_storage_unit(self, room_id: str, name: str, unit_type: str, model_number: str = "") -> StorageUnit:
        """Create a storage unit (-80C, -20C, 4C, LN2). Agent: @agent: eln-api-agent"""
        with self._lock:
            if room_id not in self._rooms:
                raise KeyError(f"Room '{room_id}' not found.")
            unit_id = f"UNIT-{uuid.uuid4().hex[:6].upper()}"
            unit = StorageUnit(unit_id=unit_id, room_id=room_id, name=name, unit_type=unit_type, model_number=model_number)
            self._units[unit_id] = unit
            return unit

    def create_rack(self, unit_id: str, name: str, shelf_level: int = 1) -> Rack:
        """Create a rack/shelf. Agent: @agent: eln-api-agent"""
        with self._lock:
            if unit_id not in self._units:
                raise KeyError(f"Storage unit '{unit_id}' not found.")
            rack_id = f"RACK-{uuid.uuid4().hex[:6].upper()}"
            rack = Rack(rack_id=rack_id, unit_id=unit_id, name=name, shelf_level=shelf_level)
            self._racks[rack_id] = rack
            return rack

    def create_box(
        self,
        rack_id: str,
        name: str,
        box_type: str = "9x9",
        temperature_target: str = "-80C",
    ) -> Box:
        """
        Create a 2D grid storage box (9x9 or 10x10).

        Agent: @agent: eln-api-agent
        Parameter rack_id (str): Rack containing box.
        Parameter name (str): Box title.
        Parameter box_type (str): '9x9' (81 slots) or '10x10' (100 slots).
        Parameter temperature_target (str): Target temperature (e.g. -80C).
        Return Type: Box
        """
        with self._lock:
            if rack_id not in self._racks:
                raise KeyError(f"Rack '{rack_id}' not found.")

            rows = 10 if box_type == "10x10" else 9
            cols = 10 if box_type == "10x10" else 9
            box_id = f"BOX-{uuid.uuid4().hex[:6].upper()}"
            box = Box(
                box_id=box_id,
                rack_id=rack_id,
                name=name,
                box_type=box_type,
                row_count=rows,
                col_count=cols,
                temperature_target=temperature_target,
            )
            self._boxes[box_id] = box
            return box

    def get_full_hierarchy(self) -> List[Dict[str, Any]]:
        """
        Return the complete nested spatial hierarchy tree (Room -> Unit -> Rack -> Box).

        Agent: @agent: eln-api-agent
        Return Type: List[Dict[str, Any]]
        """
        with self._lock:
            hierarchy: List[Dict[str, Any]] = []
            for room in self._rooms.values():
                r_dict = room.to_dict()
                r_dict["units"] = []
                for unit in [u for u in self._units.values() if u.room_id == room.room_id]:
                    u_dict = unit.to_dict()
                    u_dict["racks"] = []
                    for rack in [rk for rk in self._racks.values() if rk.unit_id == unit.unit_id]:
                        rk_dict = rack.to_dict()
                        rk_dict["boxes"] = [b.to_dict() for b in self._boxes.values() if b.rack_id == rack.rack_id]
                        u_dict["racks"].append(rk_dict)
                    r_dict["units"].append(u_dict)
                hierarchy.append(r_dict)
            return hierarchy

    # -------------------------------------------------------------------------
    # 2D BOX GRID OCCUPANCY MANAGEMENT
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_slot(slot: str, max_rows: int, max_cols: int) -> str:
        """
        Validate and normalize coordinate string (e.g. 'a1' -> 'A1').

        Agent: @agent: eln-api-agent
        """
        slot_clean = slot.strip().upper()
        match = re.match(r"^([A-Z])(\d+)$", slot_clean)
        if not match:
            raise ValueError(f"Invalid coordinate format '{slot}'. Must be letter row + number col (e.g. A1, I9).")

        row_letter, col_num_str = match.groups()
        row_idx = ord(row_letter) - ord("A")
        col_idx = int(col_num_str) - 1

        if not (0 <= row_idx < max_rows):
            raise ValueError(f"Row '{row_letter}' is out of bounds for box with {max_rows} rows.")
        if not (0 <= col_idx < max_cols):
            raise ValueError(f"Column '{col_num_str}' is out of bounds for box with {max_cols} columns.")

        return f"{row_letter}{col_num_str}"

    def get_box_grid(self, box_id: str) -> Dict[str, Any]:
        """
        Generate 2D matrix of box slots showing occupancy, tube details, and percentage full.

        Agent: @agent: eln-api-agent
        Parameter box_id (str): Target box ID.
        Return Type: Dict[str, Any]
        """
        with self._lock:
            box = self._boxes.get(box_id)
            if not box:
                raise KeyError(f"Box '{box_id}' not found.")

            # Find all tubes residing in this box
            box_tubes = {t.slot: t for t in self._tubes.values() if t.box_id == box_id}

            row_letters = [chr(ord("A") + r) for r in range(box.row_count)]
            col_numbers = list(range(1, box.col_count + 1))

            grid: List[List[Dict[str, Any]]] = []
            occupied_count = 0

            for r_letter in row_letters:
                row_slots: List[Dict[str, Any]] = []
                for c_num in col_numbers:
                    slot_coord = f"{r_letter}{c_num}"
                    tube = box_tubes.get(slot_coord)
                    if tube:
                        occupied_count += 1
                        row_slots.append(
                            {
                                "slot": slot_coord,
                                "status": "occupied",
                                "tube": {
                                    "tube_id": tube.tube_id,
                                    "barcode": tube.barcode,
                                    "sample_name": tube.sample_name,
                                    "concentration_mg_ml": tube.concentration_mg_ml,
                                    "volume_ul": tube.volume_ul,
                                    "construct_id": tube.construct_id,
                                },
                            }
                        )
                    else:
                        row_slots.append({"slot": slot_coord, "status": "empty", "tube": None})
                grid.append(row_slots)

            total_slots = box.row_count * box.col_count
            free_count = total_slots - occupied_count
            occupancy_pct = round((occupied_count / total_slots) * 100.0, 1)

            return {
                "box_id": box.box_id,
                "name": box.name,
                "box_type": box.box_type,
                "temperature_target": box.temperature_target,
                "row_count": box.row_count,
                "col_count": box.col_count,
                "total_slots": total_slots,
                "occupied_count": occupied_count,
                "free_count": free_count,
                "occupancy_percent": occupancy_pct,
                "grid": grid,
            }

    def place_tube(
        self,
        box_id: str,
        slot: str,
        sample_name: str,
        volume_ul: float,
        concentration_mg_ml: Optional[float] = None,
        barcode: Optional[str] = None,
        construct_id: Optional[str] = None,
        pool_id: Optional[str] = None,
        daily_entry_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        nanodrop_id: Optional[str] = None,
        notes: str = "",
        user_id: str = "active_researcher",
    ) -> Tube:
        """
        Place a new sample tube into a designated box slot, verifying slot availability.

        Agent: @agent: eln-api-agent
        Parameter box_id (str): Target box ID.
        Parameter slot (str): Coordinate slot (e.g. 'A1', 'I9').
        Parameter sample_name (str): Label for sample.
        Parameter volume_ul (float): Aliquot volume in microliters.
        Parameter concentration_mg_ml (Optional[float]): Concentration in mg/mL.
        Parameter barcode (Optional[str]): 2D barcode (auto-generated if omitted).
        Parameter construct_id (Optional[str]): Source construct ID.
        Parameter pool_id (Optional[str]): Source FPLC pool ID.
        Parameter daily_entry_id (Optional[str]): Origin daily notebook entry ID.
        Parameter campaign_id (Optional[str]): Origin experimental campaign ID.
        Parameter nanodrop_id (Optional[str]): Associated NanoDrop measurement ID.
        Parameter notes (str): Notes.
        Parameter user_id (str): Operator placing tube.
        Return Type: Tube
        """
        with self._lock:
            box = self._boxes.get(box_id)
            if not box:
                raise KeyError(f"Box '{box_id}' not found.")

            norm_slot = self._validate_slot(slot, box.row_count, box.col_count)

            # Check if slot already occupied
            existing = next((t for t in self._tubes.values() if t.box_id == box_id and t.slot == norm_slot), None)
            if existing:
                raise ValueError(
                    f"Slot '{norm_slot}' in Box '{box_id}' is already occupied by Tube '{existing.tube_id}' ({existing.sample_name})."
                )

            tube_id = f"TUBE-{uuid.uuid4().hex[:8].upper()}"
            bc = barcode or f"BC-{uuid.uuid4().hex[:8].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()

            tube = Tube(
                tube_id=tube_id,
                barcode=bc,
                sample_name=sample_name,
                box_id=box_id,
                slot=norm_slot,
                volume_ul=volume_ul,
                concentration_mg_ml=concentration_mg_ml,
                construct_id=construct_id,
                pool_id=pool_id,
                daily_entry_id=daily_entry_id,
                campaign_id=campaign_id,
                nanodrop_id=nanodrop_id,
                notes=notes,
                created_by=user_id,
                created_at=now_iso,
                updated_at=now_iso,
            )
            self._tubes[tube_id] = tube

            self._audit_service.record_event(
                entity_type="tube",
                entity_id=tube_id,
                action="PLACE_TUBE",
                performed_by=user_id,
                previous_state=None,
                new_state=tube.to_dict(),
                metadata={"box_id": box_id, "slot": norm_slot, "barcode": bc},
            )
            return tube

    def move_tube(
        self,
        tube_id: str,
        target_box_id: str,
        target_slot: str,
        user_id: str = "active_researcher",
        reason: str = "Routine inventory relocation",
    ) -> Dict[str, Any]:
        """
        Relocate a tube to a new box coordinate with an immutable audit log entry.

        Agent: @agent: eln-api-agent
        Parameter tube_id (str): Target tube ID.
        Parameter target_box_id (str): Destination box ID.
        Parameter target_slot (str): Destination coordinate (e.g. 'C4').
        Parameter user_id (str): Operator executing move.
        Parameter reason (str): Scientific or operational reason for movement.
        Return Type: Dict[str, Any]
        """
        with self._lock:
            tube = self._tubes.get(tube_id)
            if not tube:
                raise KeyError(f"Tube '{tube_id}' not found.")

            target_box = self._boxes.get(target_box_id)
            if not target_box:
                raise KeyError(f"Destination Box '{target_box_id}' not found.")

            norm_slot = self._validate_slot(target_slot, target_box.row_count, target_box.col_count)

            # Check if target slot occupied
            occupied_by = next(
                (t for t in self._tubes.values() if t.box_id == target_box_id and t.slot == norm_slot and t.tube_id != tube_id),
                None,
            )
            if occupied_by:
                raise ValueError(
                    f"Destination slot '{norm_slot}' in Box '{target_box_id}' is occupied by Tube '{occupied_by.tube_id}'."
                )

            prev_state = tube.to_dict()
            old_box_id = tube.box_id
            old_slot = tube.slot

            tube.box_id = target_box_id
            tube.slot = norm_slot
            tube.updated_at = datetime.now(timezone.utc).isoformat()

            audit_evt = self._audit_service.record_event(
                entity_type="tube",
                entity_id=tube_id,
                action="TUBE_MOVE",
                performed_by=user_id,
                previous_state=prev_state,
                new_state=tube.to_dict(),
                metadata={
                    "from_box": old_box_id,
                    "from_slot": old_slot,
                    "to_box": target_box_id,
                    "to_slot": norm_slot,
                    "reason": reason,
                },
            )

            return {
                "tube_id": tube_id,
                "from_box": old_box_id,
                "from_slot": old_slot,
                "to_box": target_box_id,
                "to_slot": norm_slot,
                "reason": reason,
                "audit_event_id": audit_evt.event_id,
                "timestamp": tube.updated_at,
            }

    # -------------------------------------------------------------------------
    # SAMPLE LINEAGE RESOLUTION
    # -------------------------------------------------------------------------

    def resolve_lineage(self, tube_id: str) -> Dict[str, Any]:
        """
        Resolve the complete upstream sample lineage tree for a given tube.

        Agent: @agent: eln-api-agent
        Traverses relationships:
            Tube -> Spatial Location (Room, Storage Unit, Rack, Box, Slot)
            Tube -> Origin Daily Notebook Entry (Day #, SOP fork, Observations)
            Tube -> FPLC Fraction Pool (Ve, mean UV280, pooled volume, yield)
            Tube -> Target Construct / Sequence Record (pI, MW, e280)
            Tube -> Master Experimental Campaign (Campaign ID, status, final yields)

        Parameter tube_id (str): Unique tube identifier.
        Return Type: Dict[str, Any]
        """
        with self._lock:
            tube = self._tubes.get(tube_id)
            if not tube:
                raise KeyError(f"Tube '{tube_id}' not found.")

            # Resolve Spatial Hierarchy
            box = self._boxes.get(tube.box_id)
            rack = self._racks.get(box.rack_id) if box else None
            unit = self._units.get(rack.unit_id) if rack else None
            room = self._rooms.get(unit.room_id) if unit else None

            location_hierarchy = {
                "room": room.to_dict() if room else None,
                "storage_unit": unit.to_dict() if unit else None,
                "rack": rack.to_dict() if rack else None,
                "box": box.to_dict() if box else None,
                "slot": tube.slot,
                "full_path": (
                    f"{room.name if room else '?'} > {unit.name if unit else '?'} > "
                    f"{rack.name if rack else '?'} > {box.name if box else '?'} > Slot {tube.slot}"
                ),
            }

            # Resolve Campaign & Daily Entry
            campaign_dict: Optional[Dict[str, Any]] = None
            daily_entry_dict: Optional[Dict[str, Any]] = None

            if tube.campaign_id:
                campaign = self._campaign_service.get_campaign(tube.campaign_id)
                if campaign:
                    campaign_dict = campaign.to_dict()
                    if tube.daily_entry_id:
                        entry = next((e for e in campaign.daily_entries if e.entry_id == tube.daily_entry_id), None)
                        if entry:
                            daily_entry_dict = entry.to_dict()

            # Resolve FPLC Fraction Pool
            fraction_pool_dict: Optional[Dict[str, Any]] = None
            if tube.pool_id:
                pool = self._fplc_service.get_pool(tube.pool_id)
                if pool:
                    fraction_pool_dict = pool.to_dict()

            # Resolve Sequence Construct
            construct_dict: Optional[Dict[str, Any]] = None
            construct_id = tube.construct_id or (fraction_pool_dict.get("construct_id") if fraction_pool_dict else None)
            if construct_id:
                construct = self._sequence_service.get_sequence(construct_id)
                if construct:
                    construct_dict = construct.to_dict()

            # Audit history for this tube
            audit_events = [e.to_dict() for e in self._audit_service.get_trail(entity_type="tube", entity_id=tube_id)]

            return {
                "tube": tube.to_dict(),
                "location": location_hierarchy,
                "campaign": campaign_dict,
                "daily_entry": daily_entry_dict,
                "fraction_pool": fraction_pool_dict,
                "construct": construct_dict,
                "nanodrop_id": tube.nanodrop_id,
                "audit_trail": audit_events,
            }

    def get_tube(self, tube_id: str) -> Optional[Tube]:
        """Retrieve tube by ID. Agent: @agent: eln-api-agent"""
        with self._lock:
            return self._tubes.get(tube_id)

    def clear_for_testing(self) -> None:
        """Reset internal inventory state. Agent: @agent: eln-api-agent"""
        with self._lock:
            self._rooms.clear()
            self._units.clear()
            self._racks.clear()
            self._boxes.clear()
            self._tubes.clear()
            self._seed_standard_freezer_infrastructure()


_global_inventory_service = InventoryService()


def get_inventory_service() -> InventoryService:
    """
    Get the process-level singleton instance of InventoryService.

    Agent: @agent: eln-api-agent
    Return Type: InventoryService
    """
    return _global_inventory_service
