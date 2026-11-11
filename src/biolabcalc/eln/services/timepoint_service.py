"""
Module: biolabcalc.eln.services.timepoint_service
Component: Kinetic Timepoint Recording, Delta t0 Resolution & Live Countdown Timers
Architectural Role: Core service providing second-resolution kinetic timepoint recording,
elapsed duration delta calculation from t0, deviation tracking against planned SOP durations,
and real-time countdown timer orchestration.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .audit_service import get_audit_service


def _parse_iso_datetime(dt_str_or_obj: Any) -> datetime:
    """
    Parse an ISO 8601 string or datetime object into a timezone-aware UTC datetime.

    Parameter dt_str_or_obj (Any): Input string or datetime.
    Return Type: datetime
    """
    if isinstance(dt_str_or_obj, datetime):
        if dt_str_or_obj.tzinfo is None:
            return dt_str_or_obj.replace(tzinfo=timezone.utc)
        return dt_str_or_obj.astimezone(timezone.utc)
    if isinstance(dt_str_or_obj, (int, float)):
        return datetime.fromtimestamp(dt_str_or_obj, tz=timezone.utc)

    # Clean string
    cleaned = str(dt_str_or_obj).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        # Fallback to standard formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"Unable to parse datetime string: {dt_str_or_obj}")


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to a signed string +HH:MM:SS or -HH:MM:SS.

    Parameter seconds (float): Duration in seconds.
    Return Type: str
    """
    sign = "+" if seconds >= 0 else "-"
    total_sec = int(abs(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    sec = total_sec % 60
    return f"{sign}{hours:02d}:{minutes:02d}:{sec:02d}"


@dataclass
class Timepoint:
    """
    Data model representing a discrete kinetic timepoint with second resolution.

    Architectural Role: Quantifies kinetic elapsed time from t0, captures operational parameters,
    and records deviation from planned protocol duration.
    """

    timepoint_id: str
    entry_id: str
    step_name: str
    t0: str
    timestamp: str
    elapsed_seconds: float
    elapsed_formatted: str
    planned_duration_seconds: Optional[float] = None
    deviation_seconds: Optional[float] = None
    deviation_percent: Optional[float] = None
    is_deviated: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    created_by: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize timepoint to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


class LiveTimer:
    """
    Active countdown/countup timer for live laboratory protocol execution.

    Architectural Role: Maintains real-time clock state for active incubations, kinetic assays,
    or harvest centrifugation, calculating remaining duration and elapsed deviation.
    """

    def __init__(
        self,
        timer_id: str,
        name: str,
        target_duration_seconds: float,
        entry_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize live timer instance.

        Parameter timer_id (str): Unique timer identifier.
        Parameter name (str): Human-readable name (e.g. 'IPTG Induction 4h').
        Parameter target_duration_seconds (float): Planned target duration in seconds.
        Parameter entry_id (Optional[str]): Daily entry ID to which timer belongs.
        Parameter metadata (Optional[Dict[str, Any]]): Contextual metadata.
        """
        self.timer_id = timer_id
        self.name = name
        self.target_duration_seconds = target_duration_seconds
        self.entry_id = entry_id
        self.metadata = metadata or {}
        self.start_epoch = time.time()
        self.start_time_iso = datetime.now(timezone.utc).isoformat()
        self.status = "running"  # running, paused, stopped, completed
        self.paused_elapsed: float = 0.0
        self.pause_epoch: Optional[float] = None

    def tick(self) -> Dict[str, Any]:
        """
        Compute instantaneous state of the timer.

        Return Type: Dict[str, Any]
        """
        if self.status == "running":
            current_elapsed = (time.time() - self.start_epoch) + self.paused_elapsed
        else:
            current_elapsed = self.paused_elapsed

        remaining = max(0.0, self.target_duration_seconds - current_elapsed)
        is_expired = current_elapsed >= self.target_duration_seconds
        deviation_seconds = current_elapsed - self.target_duration_seconds if is_expired else 0.0
        progress_pct = (
            min(100.0, (current_elapsed / self.target_duration_seconds) * 100.0)
            if self.target_duration_seconds > 0
            else 100.0
        )

        return {
            "timer_id": self.timer_id,
            "name": self.name,
            "entry_id": self.entry_id,
            "status": self.status,
            "start_time": self.start_time_iso,
            "target_duration_seconds": self.target_duration_seconds,
            "elapsed_seconds": round(current_elapsed, 1),
            "elapsed_formatted": format_duration(current_elapsed),
            "remaining_seconds": round(remaining, 1),
            "remaining_formatted": format_duration(remaining),
            "is_expired": is_expired,
            "deviation_seconds": round(deviation_seconds, 1),
            "progress_percent": round(progress_pct, 1),
        }

    def pause(self) -> None:
        """
        Pause the running timer.

        """
        if self.status == "running":
            self.paused_elapsed += time.time() - self.start_epoch
            self.status = "paused"

    def resume(self) -> None:
        """
        Resume a paused timer.

        """
        if self.status == "paused":
            self.start_epoch = time.time()
            self.status = "running"

    def stop(self) -> Dict[str, Any]:
        """
        Stop timer and finalize state.

        Return Type: Dict[str, Any]
        """
        self.status = "stopped"
        return self.tick()


class TimepointService:
    """
    Service managing second-resolution kinetic timepoint recording and live timers.

    Architectural Role: Encapsulates kinetic calculations, deviation thresholding against SOP
    benchmarks, and coordinates live active timers.
    """

    def __init__(self, deviation_tolerance_seconds: float = 60.0) -> None:
        """
        Initialize TimepointService.

        Parameter deviation_tolerance_seconds (float): Grace window before marking a duration
        as deviated (default: 60.0s).
        """
        self._lock = threading.RLock()
        self._timepoints: Dict[str, Timepoint] = {}
        self._live_timers: Dict[str, LiveTimer] = {}
        self._tolerance_seconds = deviation_tolerance_seconds
        self._audit_service = get_audit_service()

    def record_timepoint(
        self,
        entry_id: str,
        step_name: str,
        t0: Any,
        timestamp: Optional[Any] = None,
        planned_duration_seconds: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
        notes: str = "",
        created_by: str = "unknown",
    ) -> Timepoint:
        """
        Record a second-resolution kinetic timepoint with elapsed delta t0 and deviation tracking.

        Calculates:
            elapsed_seconds = (timestamp - t0).total_seconds()
            deviation_seconds = elapsed_seconds - planned_duration_seconds (if planned provided)
            deviation_percent = (deviation_seconds / planned_duration_seconds) * 100.0
            is_deviated = abs(deviation_seconds) > tolerance

        Parameter entry_id (str): Daily notebook entry ID.
        Parameter step_name (str): Label for experimental step (e.g. 'OD600 Measurement t=1h').
        Parameter t0 (Any): Anchor start datetime (ISO string or datetime).
        Parameter timestamp (Optional[Any]): Actual measurement time (defaults to now UTC).
        Parameter planned_duration_seconds (Optional[float]): SOP targeted elapsed seconds.
        Parameter parameters (Optional[Dict[str, Any]]): Experimental readings (e.g. OD600=0.62).
        Parameter notes (str): Operator observations.
        Parameter created_by (str): Operator ID.
        Return Type: Timepoint
        """
        with self._lock:
            dt_t0 = _parse_iso_datetime(t0)
            dt_now = _parse_iso_datetime(timestamp) if timestamp is not None else datetime.now(timezone.utc)

            elapsed_sec = (dt_now - dt_t0).total_seconds()
            elapsed_sec = round(elapsed_sec, 2)
            elapsed_formatted = format_duration(elapsed_sec)

            dev_sec: Optional[float] = None
            dev_pct: Optional[float] = None
            is_deviated = False

            if planned_duration_seconds is not None and planned_duration_seconds > 0:
                dev_sec = round(elapsed_sec - planned_duration_seconds, 2)
                dev_pct = round((dev_sec / planned_duration_seconds) * 100.0, 2)
                is_deviated = abs(dev_sec) > self._tolerance_seconds

            timepoint_id = f"TP-{uuid.uuid4().hex[:8].upper()}"
            timepoint = Timepoint(
                timepoint_id=timepoint_id,
                entry_id=entry_id,
                step_name=step_name,
                t0=dt_t0.isoformat(),
                timestamp=dt_now.isoformat(),
                elapsed_seconds=elapsed_sec,
                elapsed_formatted=elapsed_formatted,
                planned_duration_seconds=planned_duration_seconds,
                deviation_seconds=dev_sec,
                deviation_percent=dev_pct,
                is_deviated=is_deviated,
                parameters=parameters or {},
                notes=notes,
                created_by=created_by,
            )
            self._timepoints[timepoint_id] = timepoint

            # Log audit event if deviation detected or for record
            if is_deviated:
                self._audit_service.record_event(
                    entity_type="timepoint",
                    entity_id=timepoint_id,
                    action="DEVIATION_DETECTED",
                    performed_by=created_by,
                    previous_state=None,
                    new_state=timepoint.to_dict(),
                    metadata={
                        "planned_duration_seconds": planned_duration_seconds,
                        "deviation_seconds": dev_sec,
                        "deviation_percent": dev_pct,
                    },
                )

            return timepoint

    def start_live_timer(
        self,
        name: str,
        target_duration_seconds: float,
        entry_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LiveTimer:
        """
        Start an active countdown timer for real-time protocol monitoring.

        Parameter name (str): Timer label.
        Parameter target_duration_seconds (float): Duration in seconds.
        Parameter entry_id (Optional[str]): Daily entry ID.
        Parameter metadata (Optional[Dict[str, Any]]): Ancillary metadata.
        Return Type: LiveTimer
        """
        with self._lock:
            timer_id = f"TMR-{uuid.uuid4().hex[:8].upper()}"
            timer = LiveTimer(
                timer_id=timer_id,
                name=name,
                target_duration_seconds=target_duration_seconds,
                entry_id=entry_id,
                metadata=metadata,
            )
            self._live_timers[timer_id] = timer
            return timer

    def get_live_timer(self, timer_id: str) -> Optional[LiveTimer]:
        """
        Get live timer by ID.

        Parameter timer_id (str): Timer identifier.
        Return Type: Optional[LiveTimer]
        """
        with self._lock:
            return self._live_timers.get(timer_id)

    def list_active_timers(self) -> List[Dict[str, Any]]:
        """
        List all active timers with real-time computed states.

        Return Type: List[Dict[str, Any]]
        """
        with self._lock:
            return [t.tick() for t in self._live_timers.values()]

    def stop_live_timer(self, timer_id: str) -> Optional[Dict[str, Any]]:
        """
        Stop and remove live timer.

        Parameter timer_id (str): Target timer ID.
        Return Type: Optional[Dict[str, Any]]
        """
        with self._lock:
            timer = self._live_timers.pop(timer_id, None)
            if timer:
                return timer.stop()
            return None

    def get_entry_timepoints(self, entry_id: str) -> List[Timepoint]:
        """
        Get all timepoints recorded for a given daily notebook entry.

        Parameter entry_id (str): Daily entry ID.
        Return Type: List[Timepoint]
        """
        with self._lock:
            return [tp for tp in self._timepoints.values() if tp.entry_id == entry_id]

    def clear_for_testing(self) -> None:
        """
        Reset internal timepoint state. For unit testing harness use only.

        """
        with self._lock:
            self._timepoints.clear()
            self._live_timers.clear()


_global_timepoint_service = TimepointService()


def get_timepoint_service() -> TimepointService:
    """
    Get the process-level singleton instance of TimepointService.

    Return Type: TimepointService
    """
    return _global_timepoint_service
