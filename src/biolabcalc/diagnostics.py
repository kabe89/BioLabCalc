"""
Module: biolabcalc.diagnostics
Component: Component 6 - Diagnostics & Failure Logging Specialist
Architectural Role: Intercepts, sanitizes, and records operational failures, CLI exceptions,
network lock collisions, database connection failures, and file permission errors.
Provides automated plain-English explanations and actionable remediation steps,
persisting to human-readable (failures.log) and machine-readable (failures.jsonl) logs.
"""

from __future__ import annotations

from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import sys
import threading
import traceback
from typing import Any, Dict, List, Optional, Tuple, Type, Union


def anonymize_path(path_str: str) -> str:
    """Strip local username and sensitive home directory hierarchy from paths."""
    if not path_str:
        return path_str
    clean = str(path_str)

    # Replace user home directory if resolvable
    try:
        home = str(Path.home())
        if home and home in clean:
            clean = clean.replace(home, "~")
    except Exception:
        pass

    try:
        expand_home = os.path.expanduser("~")
        if expand_home and expand_home in clean:
            clean = clean.replace(expand_home, "~")
    except Exception:
        pass

    # Windows user profile pattern: C:\Users\<user> or C:/Users/<user>
    clean = re.sub(r"[A-Za-z]:[\\/][Uu]sers[\\/][^\\/]+", "~", clean)
    # Unix user home patterns: /home/<user> or /Users/<user>
    clean = re.sub(r"/(?:home|Users)/[^/]+", "~", clean)

    # Redact current system username if present in clean text
    try:
        user = getpass.getuser()
        if user and len(user) > 2 and user in clean:
            clean = re.sub(re.escape(user), "[USER]", clean, flags=re.IGNORECASE)
    except Exception:
        pass

    return clean


def sanitize_message(msg: str) -> str:
    """Sanitize log messages by redacting auth tokens, passwords, and sensitive paths."""
    if not msg:
        return ""
    sanitized = str(msg)
    # Redact Authorization header / Bearer tokens
    sanitized = re.sub(
        r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}",
        r"\1[REDACTED_TOKEN]",
        sanitized,
        flags=re.IGNORECASE,
    )
    # Redact passwords in connection URLs (e.g. postgresql://user:pass@host)
    sanitized = re.sub(r"(://[^:]+:)[^@]+(@)", r"\1[REDACTED_PASS]\2", sanitized)
    # Redact user paths and usernames
    sanitized = anonymize_path(sanitized)
    return sanitized


def sanitize_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize context dictionary values."""
    sanitized: Dict[str, Any] = {}
    for k, v in ctx.items():
        if isinstance(v, str):
            sanitized[k] = sanitize_message(v)
        elif isinstance(v, dict):
            sanitized[k] = sanitize_context(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_message(item) if isinstance(item, str) else item for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


def get_sanitized_traceback(error: Union[BaseException, Type[BaseException], str]) -> str:
    """Extract and anonymize stack traceback for exception or current execution frame."""
    tb_str = ""
    if isinstance(error, BaseException) and error.__traceback__ is not None:
        tb_str = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
    elif sys.exc_info()[2] is not None:
        tb_str = traceback.format_exc()
    else:
        if isinstance(error, BaseException):
            tb_str = f"{type(error).__name__}: {str(error)}\n  (No active stack frame available)"
        elif isinstance(error, type) and issubclass(error, BaseException):
            tb_str = f"{error.__name__}\n  (No active stack frame available)"
        else:
            tb_str = f"Error: {error}\n  (No active stack frame available)"
    return sanitize_message(tb_str)


def classify_error(
    error: Union[BaseException, Type[BaseException], str],
    subsystem: str = "",
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, str, List[str]]:
    """
    Classify error and generate plain-English cause explanation and bulleted remediation steps.

    Returns:
        Tuple of (error_type, error_message, plain_english_cause, remediation_suggestions)
    """
    if isinstance(error, BaseException):
        error_type = error.__class__.__name__
        error_msg = str(error)
    elif isinstance(error, type) and issubclass(error, BaseException):
        error_type = error.__name__
        error_msg = ""
    else:
        error_type = "OperationalError"
        error_msg = str(error)

    subsystem_clean = str(subsystem).upper() if subsystem else "GENERAL"
    combined_text = f"{error_type} {error_msg} {subsystem_clean}".lower()
    errno_val = getattr(error, "errno", None)

    # 1. Network timeout / disconnected share
    is_network_timeout = (
        isinstance(
            error,
            (
                TimeoutError,
                ConnectionError,
                ConnectionResetError,
                ConnectionRefusedError,
                ConnectionAbortedError,
                BrokenPipeError,
            ),
        )
        or any(
            t in error_type.lower()
            for t in (
                "timeout",
                "connecttimeout",
                "readtimeout",
                "connectionerror",
            )
        )
        or any(
            k in combined_text
            for k in (
                "timeout",
                "timed out",
                "disconnected",
                "connection reset",
                "connection refused",
                "connection aborted",
                "network unreachable",
                "network share",
                "network drive",
                "vpn",
                "smb",
                "nfs",
                "offline mode",
            )
        )
        or (
            subsystem_clean in ("NETWORK_DRIVE", "NETWORK")
            and any(k in combined_text for k in ("fail", "error", "drop", "unreachable"))
        )
    )

    # 2. Lock collision
    is_lock_collision = (
        isinstance(error, BlockingIOError)
        or any(
            t in error_type.lower()
            for t in ("lock", "collision", "busy")
        )
        or any(
            k in combined_text
            for k in (
                "database is locked",
                "table is locked",
                "lock collision",
                "lock timeout",
                "lock error",
                "resource temporarily unavailable",
                "database busy",
                "sqlite_busy",
                "sqlite_locked",
            )
        )
        or (
            subsystem_clean == "DATABASE"
            and any(k in combined_text for k in ("lock", "busy", "collision"))
        )
    )

    # 3. Permission denied
    is_permission_denied = (
        isinstance(error, PermissionError)
        or error_type in ("PermissionError", "AccessDeniedError")
        or errno_val in (13, 1)  # EACCES, EPERM
        or any(
            k in combined_text
            for k in (
                "permission denied",
                "access denied",
                "access is denied",
                "operation not permitted",
                "forbidden",
            )
        )
    )

    # 4. Missing file
    is_missing_file = (
        isinstance(error, FileNotFoundError)
        or error_type in ("FileNotFoundError", "NoSuchFileError")
        or errno_val == 2  # ENOENT
        or any(
            k in combined_text
            for k in (
                "no such file",
                "file not found",
                "cannot find the file",
                "path does not exist",
            )
        )
    )

    # 5. Format error
    is_format_error = (
        isinstance(error, (ValueError, KeyError))
        or error_type in ("ValueError", "KeyError", "JSONDecodeError", "ParseError", "SchemaError")
        or subsystem_clean in ("PARSER", "SCHEMA")
        or any(
            k in combined_text
            for k in (
                "format",
                "invalid format",
                "malformed",
                "syntax error",
                "unrecognized format",
                "schema violation",
            )
        )
    )

    # Evaluate in precedence order
    if is_network_timeout:
        cause = "Network timeout or disconnected lab share encountered while accessing resources."
        remediations = [
            "Check if network drive/VPN is connected or switch to offline mode",
            "Verify network cable or Wi-Fi connectivity and lab VPN authentication status",
            "Confirm that the network volume is mounted and responsive",
            "Switch BioLabCalc to local offline cache mode (--env offline) if working disconnected",
        ]
    elif is_lock_collision:
        cause = "Another user or process is writing to the database; retry in a few moments"
        remediations = [
            "Another user or process is writing to the database; retry in a few moments",
            "Ensure concurrent batch ingestion or background jobs have completed",
            "Increase database lock timeout in config.yaml (database.lock_timeout_seconds)",
            "Check for and safely clear stale lock files on the shared volume if no writers are active",
        ]
    elif is_permission_denied:
        cause = "Write access denied on directory; check file permissions or run with designated user"
        remediations = [
            "Write access denied on directory; check file permissions or run with designated user",
            "Inspect read/write permissions on the target directory and parent volume",
            "Ensure your user account has write privileges for the lab directory",
            "Run the operation with the designated service account or elevated permissions",
        ]
    elif is_missing_file:
        cause = "The requested file or resource could not be found at the specified path."
        remediations = [
            "Verify file path and check format matches requirements",
            "Confirm that the target file exists and the path is spelled correctly",
            "Verify relative versus absolute path resolution from current working directory",
            "Ensure the file has not been moved, renamed, or deleted",
        ]
    elif is_format_error:
        cause = "Input data or file format does not match expected schema requirements."
        remediations = [
            "Verify file path and check format matches requirements",
            "Inspect file headers, column names, delimiters, and data types",
            "Ensure document structure matches the required schema or template specification",
            "Run with validation flags to pinpoint specific line or formatting issues",
        ]
    elif subsystem_clean == "DATABASE":
        cause = "Database operational failure or connection issue encountered."
        remediations = [
            "Verify database server connectivity and connection URL",
            "Check database schema integrity and ensure migrations are applied",
            "Confirm that the database file or server process is accessible",
        ]
    elif subsystem_clean == "CLI":
        cause = "CLI operational error occurred during command execution."
        remediations = [
            "Check command syntax and arguments using --help",
            "Review input parameters and ensure required flags are provided",
            "Inspect the diagnostics log for more details",
        ]
    else:
        cause = f"Operational failure encountered in subsystem '{subsystem_clean}': {error_type}."
        remediations = [
            "Check system logs and diagnostic details",
            "Review input parameters and retry the operation",
            "Contact your laboratory system administrator if the issue persists",
        ]

    return error_type, error_msg, cause, remediations


class DiagnosticCaptureContext:
    """Context manager for intercepting and recording operational failures."""

    def __init__(
        self,
        recorder: "FailureDiagnosticsRecorder",
        subsystem: str,
        context: Optional[Dict[str, Any]] = None,
        custom_remediation: Optional[Union[List[str], str]] = None,
        reraise: bool = True,
    ):
        self.recorder = recorder
        self.subsystem = subsystem
        self.context = context
        self.custom_remediation = custom_remediation
        self.reraise = reraise
        self.failure: Optional[Dict[str, Any]] = None
        self.exception: Optional[BaseException] = None

    def __enter__(self) -> "DiagnosticCaptureContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_val is not None:
            self.exception = exc_val
            self.failure = self.recorder.record_failure(
                subsystem=self.subsystem,
                error=exc_val,
                context=self.context,
                custom_remediation=self.custom_remediation,
            )
            # Return True to suppress exception, False to propagate/reraise
            return not self.reraise
        return False


class FailureDiagnosticsRecorder:
    """
    Component 6: Diagnostics & Failure Logging Recorder.
    Intercepts operational failures, CLI exceptions, network lock collisions,
    database connection failures, and file permission errors.
    Automatically generates plain-English causes and actionable remediation advice,
    persisting human-readable (failures.log) and machine-readable (failures.jsonl) records.
    """

    def __init__(
        self,
        log_path: Union[str, Path] = "failures.log",
        jsonl_path: Union[str, Path] = "failures.jsonl",
        log_dir: Optional[Union[str, Path]] = None,
    ):
        if log_dir is not None:
            dir_path = Path(log_dir)
            self.log_path = dir_path / "failures.log"
            self.jsonl_path = dir_path / "failures.jsonl"
        else:
            self.log_path = Path(log_path)
            self.jsonl_path = Path(jsonl_path)

        self._lock = threading.Lock()
        self._in_memory_records: List[Dict[str, Any]] = []

    def record_failure(
        self,
        subsystem: str,
        error: Union[BaseException, Type[BaseException], str],
        context: Optional[Dict[str, Any]] = None,
        custom_remediation: Optional[Union[List[str], str]] = None,
    ) -> Dict[str, Any]:
        """
        Intercept and record an operational failure.

        Parameters:
            subsystem: Component name (e.g., CLI, NETWORK_DRIVE, DATABASE, BLOB_STORE, PARSER).
            error: Exception instance, exception class, or error message string.
            context: Optional dictionary with operational metadata.
            custom_remediation: Optional custom string or list of remediation steps.

        Returns:
            Formatted failure record dictionary.
        """
        error_type, raw_msg, plain_cause, remediations = classify_error(
            error=error,
            subsystem=subsystem,
            context=context,
        )

        sanitized_msg = sanitize_message(raw_msg)
        sanitized_tb = get_sanitized_traceback(error)

        if custom_remediation:
            if isinstance(custom_remediation, str):
                custom_steps = [custom_remediation]
            else:
                custom_steps = list(custom_remediation)
            remediations = custom_steps + [r for r in remediations if r not in custom_steps]

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        subsystem_str = str(subsystem).upper() if subsystem else "GENERAL"

        record: Dict[str, Any] = {
            "timestamp": timestamp,
            "subsystem": subsystem_str,
            "error_type": error_type,
            "error_message": sanitized_msg,
            "plain_english_cause": plain_cause,
            "remediation_suggestions": remediations,
            "sanitized_traceback": sanitized_tb,
        }

        if context is not None:
            record["context"] = sanitize_context(context)

        with self._lock:
            self._in_memory_records.append(record)
            self._append_to_logs(record)

        return record

    def _append_to_logs(self, record: Dict[str, Any]) -> None:
        """Append formatted failure to human-readable log and machine-readable JSONL."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        # 1. Human-readable failures.log
        human_text = self._format_human_readable(record)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(human_text)
        except OSError as e:
            sys.stderr.write(f"[FailureDiagnosticsRecorder] Log append error: {e}\n")

        # 2. Machine-readable failures.jsonl
        try:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as e:
            sys.stderr.write(f"[FailureDiagnosticsRecorder] JSONL append error: {e}\n")

    def _format_human_readable(self, record: Dict[str, Any]) -> str:
        """Format record into a clean, human-readable log block."""
        timestamp = record.get("timestamp", "")
        subsystem = record.get("subsystem", "GENERAL")
        error_type = record.get("error_type", "Error")
        error_message = record.get("error_message", "")
        cause = record.get("plain_english_cause", "")
        remediations = record.get("remediation_suggestions", [])
        tb = record.get("sanitized_traceback", "")
        context = record.get("context")

        lines = [
            "=" * 80,
            f"[{timestamp}] [{subsystem}] {error_type}: {error_message}",
            "-" * 80,
            f"Cause: {cause}",
            "Remediation Suggestions:",
        ]
        for step in remediations:
            lines.append(f"  * {step}")

        if context:
            lines.append("Context:")
            for k, v in context.items():
                lines.append(f"  - {k}: {v}")

        if tb:
            lines.append("Traceback:")
            lines.append(tb.rstrip())

        lines.append("=" * 80)
        lines.append("")
        return "\n".join(lines)

    def get_recent_failures(
        self,
        limit: int = 10,
        newest_first: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent failure records.

        Parameters:
            limit: Maximum number of recent failures to return (default 10).
            newest_first: If True, returns newest failure first. Defaults to False (chronological).

        Returns:
            List of failure record dictionaries.
        """
        with self._lock:
            records: List[Dict[str, Any]] = []
            if self.jsonl_path.is_file():
                try:
                    with open(self.jsonl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            clean_line = line.strip()
                            if clean_line:
                                try:
                                    records.append(json.loads(clean_line))
                                except Exception:
                                    pass
                except OSError:
                    pass

            if not records and self._in_memory_records:
                records = list(self._in_memory_records)

            recent = records[-limit:] if limit > 0 else records
            if newest_first:
                recent = list(reversed(recent))
            return recent

    def clear_failures(self) -> None:
        """Clear all in-memory and persistent failure logs."""
        with self._lock:
            self._in_memory_records.clear()
            try:
                if self.log_path.exists():
                    with open(self.log_path, "w", encoding="utf-8") as f:
                        f.truncate(0)
            except OSError:
                pass

            try:
                if self.jsonl_path.exists():
                    with open(self.jsonl_path, "w", encoding="utf-8") as f:
                        f.truncate(0)
            except OSError:
                pass

    def capture_diagnostics(
        self,
        subsystem: str,
        context: Optional[Dict[str, Any]] = None,
        custom_remediation: Optional[Union[List[str], str]] = None,
        reraise: bool = True,
    ) -> DiagnosticCaptureContext:
        """Context manager to intercept and record failures within a block."""
        return DiagnosticCaptureContext(
            recorder=self,
            subsystem=subsystem,
            context=context,
            custom_remediation=custom_remediation,
            reraise=reraise,
        )


# Global default recorder instance
_default_recorder = FailureDiagnosticsRecorder()


def get_default_recorder() -> FailureDiagnosticsRecorder:
    """Get the active global default FailureDiagnosticsRecorder."""
    return _default_recorder


def set_default_recorder(recorder: FailureDiagnosticsRecorder) -> None:
    """Set the active global default FailureDiagnosticsRecorder."""
    global _default_recorder
    _default_recorder = recorder


def record_failure(
    subsystem: str,
    error: Union[BaseException, Type[BaseException], str],
    context: Optional[Dict[str, Any]] = None,
    custom_remediation: Optional[Union[List[str], str]] = None,
) -> Dict[str, Any]:
    """Intercept and record an operational failure using default recorder."""
    return _default_recorder.record_failure(
        subsystem=subsystem,
        error=error,
        context=context,
        custom_remediation=custom_remediation,
    )


def get_recent_failures(
    limit: int = 10,
    newest_first: bool = False,
) -> List[Dict[str, Any]]:
    """Retrieve recent failure records from default recorder."""
    return _default_recorder.get_recent_failures(
        limit=limit,
        newest_first=newest_first,
    )


def clear_failures() -> None:
    """Clear failure logs from default recorder."""
    _default_recorder.clear_failures()


def capture_diagnostics(
    subsystem: str,
    context: Optional[Dict[str, Any]] = None,
    custom_remediation: Optional[Union[List[str], str]] = None,
    reraise: bool = True,
) -> DiagnosticCaptureContext:
    """Context manager to intercept and record failures using default recorder."""
    return _default_recorder.capture_diagnostics(
        subsystem=subsystem,
        context=context,
        custom_remediation=custom_remediation,
        reraise=reraise,
    )


__all__ = [
    "FailureDiagnosticsRecorder",
    "DiagnosticCaptureContext",
    "classify_error",
    "anonymize_path",
    "sanitize_message",
    "sanitize_context",
    "get_sanitized_traceback",
    "record_failure",
    "get_recent_failures",
    "clear_failures",
    "capture_diagnostics",
    "get_default_recorder",
    "set_default_recorder",
]
