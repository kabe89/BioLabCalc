"""Formal Elm Architecture (TEA) State Engine and Runtime for BioLabCalc v0.4.0.

Adheres strictly to TEA principles:
- Model: Immutable frozen dataclass with pure tuple collections.
- Msg: Strongly-typed algebraic message hierarchy.
- Cmd: Declarative command requests returned from update.
- update: Pure state transition function `update(msg, model) -> (new_model, cmd)`.
- view: Pure functional rendering of model state to Markdown or text.
- Time-travel: Full undo and redo history tracking via immutable model snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple, Union

from .plasmid import PlasmidRecord, get_plasmid
from .plasmid_engineering import EngineeredPlasmidResult, engineer_plasmid
from .restriction_engine import RestrictionDigestPrediction, predict_restriction_digest


# ---------------------------------------------------------------------------
# TEA Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BioLabModel:
    """Immutable state model for the BioLabCalc runtime following Elm architecture."""
    current_plasmid: Optional[PlasmidRecord] = None
    digest_prediction: Optional[RestrictionDigestPrediction] = None
    engineering_result: Optional[EngineeredPlasmidResult] = None
    selected_enzymes: Tuple[str, ...] = ()
    view_mode: str = "summary"
    status_message: str = "Ready"
    history_undo: Tuple[Any, ...] = ()
    history_redo: Tuple[Any, ...] = ()


def _snapshot(model: BioLabModel) -> BioLabModel:
    """Create a lightweight snapshot of model state with detached history."""
    return replace(model, history_undo=(), history_redo=())


# ---------------------------------------------------------------------------
# TEA Messages
# ---------------------------------------------------------------------------

class Msg:
    """Base class for all TEA messages."""
    pass


@dataclass(frozen=True)
class LoadPlasmidMsg(Msg):
    """Load a plasmid by PlasmidRecord instance or standard catalog name."""
    plasmid: Union[PlasmidRecord, str]


@dataclass(frozen=True)
class SelectEnzymesMsg(Msg):
    """Update the set of currently selected restriction enzymes."""
    enzymes: Tuple[str, ...]


@dataclass(frozen=True)
class RunDigestMsg(Msg):
    """Run in-silico restriction digest on the currently loaded plasmid."""
    dna_mass_ug: float = 1.0
    ladder_key: str = "1kb_dna"


@dataclass(frozen=True)
class InsertGeneMsg(Msg):
    """Engineer recombinant gene insertion into the current plasmid vector."""
    gene_name: str
    sequence: str
    mode: str = "restriction_ligation"
    enzyme_5: str = "BamHI"
    enzyme_3: str = "XhoI"


@dataclass(frozen=True)
class SetViewModeMsg(Msg):
    """Switch active UI/view layout mode (e.g. summary, features, gel, engineering)."""
    view_mode: str


@dataclass(frozen=True)
class UndoMsg(Msg):
    """Revert model to the preceding state in undo history."""
    pass


@dataclass(frozen=True)
class RedoMsg(Msg):
    """Re-apply the next state from redo history."""
    pass


# ---------------------------------------------------------------------------
# TEA Command
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Cmd:
    """Declarative command describing side effects or notifications."""
    action: str = "none"
    payload: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pure Update Function
# ---------------------------------------------------------------------------

def update(msg: Msg, model: BioLabModel) -> Tuple[BioLabModel, Cmd]:
    """Pure Elm update function: takes a Msg and Model, returning (new_Model, Cmd)."""
    # Undo / Redo Time Travel
    if isinstance(msg, UndoMsg):
        if not model.history_undo:
            return replace(model, status_message="Nothing to undo"), Cmd(action="none")
        prev_snap = model.history_undo[-1]
        new_undo = model.history_undo[:-1]
        current_snap = _snapshot(model)
        new_redo = model.history_redo + (current_snap,)
        restored = replace(
            prev_snap,
            history_undo=new_undo,
            history_redo=new_redo,
            status_message=f"Undid to state with plasmid: {prev_snap.current_plasmid.name if prev_snap.current_plasmid else 'None'}",
        )
        return restored, Cmd(action="undo_applied")

    if isinstance(msg, RedoMsg):
        if not model.history_redo:
            return replace(model, status_message="Nothing to redo"), Cmd(action="none")
        next_snap = model.history_redo[-1]
        new_redo = model.history_redo[:-1]
        current_snap = _snapshot(model)
        new_undo = model.history_undo + (current_snap,)
        restored = replace(
            next_snap,
            history_undo=new_undo,
            history_redo=new_redo,
            status_message=f"Redid to state with plasmid: {next_snap.current_plasmid.name if next_snap.current_plasmid else 'None'}",
        )
        return restored, Cmd(action="redo_applied")

    # State-mutating messages: capture snapshot for undo history
    curr_snap = _snapshot(model)
    next_undo = model.history_undo + (curr_snap,)
    next_redo: Tuple[Any, ...] = ()

    if isinstance(msg, LoadPlasmidMsg):
        try:
            if isinstance(msg.plasmid, str):
                p_record = get_plasmid(msg.plasmid)
            else:
                p_record = msg.plasmid
            new_model = replace(
                model,
                current_plasmid=p_record,
                digest_prediction=None,
                engineering_result=None,
                status_message=f"Loaded plasmid '{p_record.name}' ({p_record.length:,} bp, {p_record.topology})",
                history_undo=next_undo,
                history_redo=next_redo,
            )
            return new_model, Cmd(action="plasmid_loaded", payload={"name": p_record.name, "length": p_record.length})
        except Exception as e:
            err_model = replace(model, status_message=f"Error loading plasmid: {str(e)}")
            return err_model, Cmd(action="error", payload={"error": str(e)})

    if isinstance(msg, SelectEnzymesMsg):
        enz_tuple = tuple(msg.enzymes)
        new_model = replace(
            model,
            selected_enzymes=enz_tuple,
            status_message=f"Selected enzymes: {', '.join(enz_tuple) if enz_tuple else 'None'}",
            history_undo=next_undo,
            history_redo=next_redo,
        )
        return new_model, Cmd(action="enzymes_selected", payload={"enzymes": list(enz_tuple)})

    if isinstance(msg, RunDigestMsg):
        if model.current_plasmid is None:
            err_model = replace(model, status_message="Cannot run digest: no plasmid loaded")
            return err_model, Cmd(action="error", payload={"error": "no plasmid loaded"})

        enzymes = list(model.selected_enzymes)
        if not enzymes:
            err_model = replace(model, status_message="Cannot run digest: no enzymes selected")
            return err_model, Cmd(action="error", payload={"error": "no enzymes selected"})

        try:
            pred = predict_restriction_digest(
                model.current_plasmid,
                enzymes=enzymes,
                dna_mass_ug=msg.dna_mass_ug,
                ladder_key=msg.ladder_key,
            )
            new_model = replace(
                model,
                digest_prediction=pred,
                status_message=f"Simulated digest with {', '.join(enzymes)}: {pred.fragment_count} fragments generated",
                history_undo=next_undo,
                history_redo=next_redo,
            )
            return new_model, Cmd(action="digest_completed", payload={"fragment_count": pred.fragment_count})
        except Exception as e:
            err_model = replace(model, status_message=f"Digest simulation error: {str(e)}")
            return err_model, Cmd(action="error", payload={"error": str(e)})

    if isinstance(msg, InsertGeneMsg):
        if model.current_plasmid is None:
            err_model = replace(model, status_message="Cannot insert gene: no plasmid vector loaded")
            return err_model, Cmd(action="error", payload={"error": "no vector loaded"})

        try:
            eng_res = engineer_plasmid(
                vector=model.current_plasmid,
                insert_seq=msg.sequence,
                gene_name=msg.gene_name,
                mode=msg.mode,  # type: ignore[arg-type]
                enzyme_5prime=msg.enzyme_5,
                enzyme_3prime=msg.enzyme_3,
            )
            new_model = replace(
                model,
                current_plasmid=eng_res.assembled_plasmid,
                engineering_result=eng_res,
                digest_prediction=eng_res.diagnostic_digest,
                status_message=f"Assembled recombinant plasmid '{eng_res.assembled_plasmid.name}' ({eng_res.assembled_plasmid.length:,} bp)",
                history_undo=next_undo,
                history_redo=next_redo,
            )
            return new_model, Cmd(
                action="gene_inserted",
                payload={"name": eng_res.assembled_plasmid.name, "in_frame": eng_res.in_frame},
            )
        except Exception as e:
            err_model = replace(model, status_message=f"Engineering assembly error: {str(e)}")
            return err_model, Cmd(action="error", payload={"error": str(e)})

    if isinstance(msg, SetViewModeMsg):
        new_model = replace(model, view_mode=msg.view_mode)
        return new_model, Cmd(action="view_mode_changed", payload={"mode": msg.view_mode})

    # Unrecognized message fallback
    return model, Cmd(action="unknown_message")


# ---------------------------------------------------------------------------
# Pure View Function
# ---------------------------------------------------------------------------

def view(model: BioLabModel, mode: str = "markdown") -> str:
    """Pure view rendering function: converts BioLabModel state to formatted text/Markdown."""
    lines: List[str] = []

    # Title & Status Bar
    lines.append("# BioLabCalc Plasmid Engineering & Gel Workbench")
    lines.append(f"**Status:** `{model.status_message}` | **View Mode:** `{model.view_mode}`")
    lines.append("")

    # Plasmid Summary Section
    if model.current_plasmid:
        p = model.current_plasmid
        lines.append("## Current Plasmid Record")
        lines.append(f"- **Name:** `{p.name}` (ID: `{p.id}`)")
        lines.append(f"- **Length:** `{p.length:,} bp`")
        lines.append(f"- **Topology:** `{p.topology.capitalize()}`")
        lines.append(f"- **GC Content:** `{p.gc_percent:.1f}%`")
        lines.append(f"- **Molecular Weight:** `{p.molecular_weight_da:,.1f} Da`")
        if p.description:
            lines.append(f"- **Description:** {p.description}")
        lines.append("")

        # Features Table
        if p.features:
            lines.append("### Plasmid Features")
            lines.append("| Feature | Type | Start | End | Strand | Length | Notes |")
            lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :--- |")
            for f in p.features[:15]:
                strand_str = "(+)" if f.strand >= 0 else "(-)"
                lines.append(f"| **{f.name}** | `{f.feature_type}` | {f.start:,} | {f.end:,} | {strand_str} | {f.length:,} bp | {f.notes} |")
            if len(p.features) > 15:
                lines.append(f"*... and {len(p.features) - 15} additional features.*")
            lines.append("")
    else:
        lines.append("## No Plasmid Vector Loaded")
        lines.append("Use `LoadPlasmidMsg('pET-28a(+)')` or `LoadPlasmidMsg('pUC19')` to load a vector.")
        lines.append("")

    # Selected Enzymes
    if model.selected_enzymes:
        lines.append("## Selected Restriction Enzymes")
        lines.append(f"- **Enzymes:** {', '.join(f'`{e}`' for e in model.selected_enzymes)}")
        lines.append("")

    # Restriction Digest Prediction Section
    if model.digest_prediction:
        dp = model.digest_prediction
        lines.append("## Restriction Digest Prediction")
        lines.append(f"- **Enzymes:** {', '.join(dp.enzymes)}")
        lines.append(f"- **Fragments:** `{dp.fragment_count}`")
        lines.append("")
        lines.append("| Fragment | Size (bp) | Mass (ng) | Rel. Intensity | Overhangs | Contained Features |")
        lines.append("| :---: | :---: | :---: | :---: | :---: | :--- |")
        for frag in dp.fragments:
            features_str = ", ".join(frag.contained_features) if frag.contained_features else "None"
            lines.append(
                f"| #{frag.fragment_id} | {frag.length_bp:,} bp | {frag.mass_ng:.1f} ng | "
                f"{frag.relative_intensity:.2f} | {frag.left_overhang_type} / {frag.right_overhang_type} | {features_str} |"
            )
        lines.append("")

    # Engineering Assembly Section
    if model.engineering_result:
        eng = model.engineering_result
        lines.append("## Gene Expression Engineering Result")
        lines.append(f"- **Target Gene:** `{eng.target_gene_name}`")
        lines.append(f"- **Cloning Mode:** `{eng.mode}`")
        lines.append(f"- **In-Frame:** `{'Yes (Aligned)' if eng.in_frame else 'NO (Frame Shift)'}`")
        lines.append(f"- **Start Codon:** `{'Yes' if eng.has_start_codon else 'No'}`")
        lines.append(f"- **Stop Codon:** `{'Yes' if eng.has_stop_codon else 'No'}`")
        lines.append(f"- **Premature Stops:** `{eng.premature_stops}`")
        lines.append(f"- **RBS / Kozak:** `{'Present' if eng.rbs_or_kozak_ok else 'Missing'}`")
        lines.append(f"- **Replication Origin:** `{'Intact' if eng.ori_intact else 'Disrupted'}`")
        lines.append(f"- **Selectable Marker:** `{'Intact' if eng.marker_intact else 'Disrupted'}`")
        lines.append(f"- **Colony PCR Amplicon:** `{eng.colony_pcr_amplicon_bp:,} bp`")
        lines.append(f"- **Expressed Protein MW:** `{eng.protein_mw_da:,.1f} Da`")
        lines.append(f"- **Extinction Coeff (280nm):** `{eng.protein_extinction_280:,} M^-1 cm^-1`")
        lines.append(f"- **Predicted E. coli Yield:** `{eng.predicted_expression_yield_mg_l:.1f} mg/L`")
        lines.append("")

        lines.append("### Designed Cloning Primers")
        lines.append(f"- **Forward Primer:** `{eng.forward_primer_full_seq}` (Tm: {eng.forward_primer.tm_celsius:.1f}°C, GC: {eng.forward_primer.gc_percent:.1f}%)")
        lines.append(f"- **Reverse Primer:** `{eng.reverse_primer_full_seq}` (Tm: {eng.reverse_primer.tm_celsius:.1f}°C, GC: {eng.reverse_primer.gc_percent:.1f}%)")
        lines.append(f"- **Primer Heterodimer Score:** `{eng.primer_heterodimer_score}`")
        lines.append("")

        if eng.notes:
            lines.append("### Engineering Notes")
            for note in eng.notes:
                lines.append(f"- {note}")
            lines.append("")

        if eng.warnings:
            lines.append("### Warnings")
            for warn in eng.warnings:
                lines.append(f"- ⚠️ {warn}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TEA Runtime Store
# ---------------------------------------------------------------------------

class TEAStore:
    """Runtime store managing immutable BioLabModel state, dispatch, and time travel."""

    def __init__(self, initial_model: Optional[BioLabModel] = None) -> None:
        self._model: BioLabModel = initial_model if initial_model is not None else BioLabModel()

    @property
    def model(self) -> BioLabModel:
        """Return the current immutable model state."""
        return self._model

    def dispatch(self, msg: Msg) -> Tuple[BioLabModel, Cmd]:
        """Dispatch a Msg to the pure update function and apply state transition."""
        new_model, cmd = update(msg, self._model)
        self._model = new_model
        return new_model, cmd

    def view(self, mode: str = "markdown") -> str:
        """Render the current model view."""
        return view(self._model, mode=mode)
