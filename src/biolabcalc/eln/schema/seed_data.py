"""
Module: biolabcalc.eln.schema.seed_data
Component: Benchmark Seed Data Generator for 5-Day T7 RNA Polymerase Campaign
Agent: @agent: eln-db-agent
Architectural Role: Generates production benchmark seed data for the complete
                    5-day T7 RNA Polymerase (pET-28a-T7RNAP, 99 kDa, 883 aa)
                    expression and purification protocol, populating all 21
                    database entities with yield metrics, completion timestamps,
                    chromatography fractions, gel lanes, and RAG vector chunks.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from biolabcalc.eln.schema.database import Session
from biolabcalc.eln.schema.models import (
    AuditLog,
    BioSequence,
    BiomoleculeType,
    CodeAnalysisRun,
    EphysRecording,
    ExptStatus,
    FileFormatCategory,
    FplcColumn,
    FplcFraction,
    FplcRun,
    FreezerBox,
    GelLane,
    GelRecord,
    InventoryTube,
    NanodropMeasurement,
    NotebookDailyEntry,
    NotebookTimepointLog,
    PcrAssay,
    RagDocumentChunk,
    SopTemplate,
    StorageBlob,
    StorageHierarchyNode,
    StorageNodeType,
    User,
    UserRole,
    ExperimentalCampaign,
)


def _generate_synthetic_embedding(seed_val: float, dim: int = 1536) -> List[float]:
    """
    Generate a normalized deterministic synthetic embedding vector.

    Parameters:
        seed_val (float): Seed offset for trig pattern.
        dim (int): Vector dimensionality. Default 1536.

    Returns:
        List[float]: L2-normalized float vector.

    Agent: @agent: eln-db-agent
    """
    raw = [math.sin(seed_val + (i * 0.05)) for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw] if norm > 0.0 else raw


def seed_campaign(session: Session) -> Dict[str, str]:
    """
    Execute comprehensive benchmark seeding for the 5-day T7 RNA Polymerase campaign.

    Parameters:
        session (Session): Active database session.

    Returns:
        Dict[str, str]: Dictionary mapping entity keys to created UUID identifiers.

    Agent: @agent: eln-db-agent
    """
    # -------------------------------------------------------------------------
    # 1. Users
    # -------------------------------------------------------------------------
    pi_user = User(
        email="eleanor.vance@biolabcalc.org",
        full_name="Dr. Eleanor Vance",
        role=UserRole.PRINCIPAL_INVESTIGATOR.value,
        department="Structural Biology & Enzymology",
        is_active=True
    )
    researcher_user = User(
        email="julian.hayes@biolabcalc.org",
        full_name="Dr. Julian Hayes",
        role=UserRole.ACTIVE_RESEARCHER.value,
        department="Recombinant Protein Core",
        is_active=True
    )
    student_user = User(
        email="maya.patel@biolabcalc.org",
        full_name="Maya Patel",
        role=UserRole.ROTATION_STUDENT.value,
        department="Biochemistry Graduate Program",
        is_active=True
    )
    alumni_user = User(
        email="arthur.pendelton@alumni.biolabcalc.org",
        full_name="Dr. Arthur Pendelton",
        role=UserRole.ALUMNI.value,
        department="Structural Biology",
        is_active=False
    )
    session.add_all([pi_user, researcher_user, student_user, alumni_user])
    session.commit()

    # -------------------------------------------------------------------------
    # 2. SOP Template
    # -------------------------------------------------------------------------
    sop_content = """# SOP-PROT-T7RNAP-01: Recombinant T7 RNA Polymerase Expression & Dual-Column FPLC Purification

## 1. Objective
To express and purify research-grade recombinant T7 RNA Polymerase (pET-28a-T7RNAP, 98.9 kDa, 883 aa)
from 2 L of BL21(DE3) bacterial culture to >95% homogeneity suitable for in vitro transcription (IVT).

## 2. Equipment & Columns
- AKTA Pure 25 FPLC System
- HisTrap HP 5 mL Ni-NTA column (Cytiva)
- Superdex 200 Increase 10/300 GL SEC column (Cytiva)
- Branson Sonifier 450 probe sonicator
- NanoDrop One UV-Vis Spectrophotometer

## 3. Buffer Formulations
- **Lysis Buffer:** 50 mM Tris-HCl pH 8.0, 300 mM NaCl, 20 mM imidazole, 5% glycerol, 1 mM DTT, 25 U/mL Benzonase, 1 mM PMSF.
- **Ni-NTA Wash Buffer:** 50 mM Tris-HCl pH 8.0, 300 mM NaCl, 50 mM imidazole, 5% glycerol, 1 mM DTT.
- **Ni-NTA Elution Buffer:** 50 mM Tris-HCl pH 8.0, 300 mM NaCl, 500 mM imidazole, 5% glycerol, 1 mM DTT.
- **SEC / Storage Buffer:** 50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM EDTA, 1 mM DTT, 50% (v/v) glycerol.

## 4. 5-Day Protocol Summary
- **Day 0:** Heat shock transformation into BL21(DE3), plating on LB + 50 ug/mL kanamycin at 37°C.
- **Day 1:** Pick single colony, inoculate 50 mL LB + Kan starter culture, shake 16 h at 37°C, 220 rpm.
- **Day 2:** Inoculate 2 L 2xYT broth (1:50). Grow at 37°C to OD600=0.68. Induce with 0.8 mM IPTG. Express at 20°C for 18 h (final OD600=3.65).
- **Day 3:** Centrifuge at 4,000 x g (22.4 g wet pellet). Resuspend in lysis buffer, sonicate on ice, centrifuge at 18,000 x g. Run HisTrap HP 5 mL FPLC. Wash at 50 mM imidazole, elute with 50-500 mM gradient. Pool peak eluate (30 mL).
- **Day 4:** Concentrate to 3.0 mL (30 kDa MWCO). Run Superdex 200 SEC polishing. Pool monomer peak B4-B8 (16 mL). Perform 4-20% SDS-PAGE (>95% purity) and NanoDrop A280 (A280=4.02, conc=2.85 mg/mL, yield=45.6 mg). Aliquot at -80°C.
"""
    sop = SopTemplate(
        title="Standard Operating Procedure: Recombinant T7 RNA Polymerase Expression & Dual-Column Purification",
        code="SOP-PROT-T7RNAP-01",
        version="2.1",
        category="Protein Production & Purification",
        content_markdown=sop_content,
        created_by=pi_user.id
    )
    session.add(sop)
    session.commit()

    # -------------------------------------------------------------------------
    # 3. Storage Hierarchy Nodes & Freezer Box
    # -------------------------------------------------------------------------
    node_facility = StorageHierarchyNode(
        name="Main Lab - Room 402",
        node_type=StorageNodeType.ROOM.value,
        temperature_c=21.0,
        barcode="LOC-LAB-402"
    )
    session.add(node_facility)
    session.commit()

    node_freezer = StorageHierarchyNode(
        parent_id=node_facility.id,
        name="-80C Ultra-Low Freezer 1 (Sanyo VIP)",
        node_type=StorageNodeType.FREEZER_MINUS80.value,
        temperature_c=-80.0,
        barcode="FRZ80-001"
    )
    session.add(node_freezer)
    session.commit()

    node_rack = StorageHierarchyNode(
        parent_id=node_freezer.id,
        name="Freezer 1 - Tower Rack 2",
        node_type=StorageNodeType.RACK.value,
        temperature_c=-80.0,
        barcode="RCK-F1-02"
    )
    session.add(node_rack)
    session.commit()

    box = FreezerBox(
        hierarchy_node_id=node_rack.id,
        name="PROT-2026-T7RNAP",
        barcode="BOX-PROT-T7RNAP-2026",
        row_count=9,
        col_count=9,
        temperature_c=-80.0,
        notes="Purified recombinant T7 RNA Polymerase glycerol stocks and working aliquots"
    )
    session.add(box)
    session.commit()

    # -------------------------------------------------------------------------
    # 4. Storage Blobs (Raw Instrument Files)
    # -------------------------------------------------------------------------
    blob_histrap = StorageBlob(
        file_name="t7_histrap_hp_run01.res",
        file_path="/storage/lims/chromatograms/2026/t7_histrap_hp_run01.res",
        file_size_bytes=1450280,
        file_hash_sha256="7a1e8c049d5bf124e5a9c8b74f014e21a812e987c2b53490fd3ea55610bc9312",
        format_category=FileFormatCategory.FPLC_RES.value,
        mime_type="application/octet-stream",
        uploaded_by=researcher_user.id
    )
    blob_sec = StorageBlob(
        file_name="t7_superdex200_run02.res",
        file_path="/storage/lims/chromatograms/2026/t7_superdex200_run02.res",
        file_size_bytes=2198400,
        file_hash_sha256="b42c98d41fe0184a28f734091c5324d86b7201cda028479e13589b917634f1ae",
        format_category=FileFormatCategory.FPLC_RES.value,
        mime_type="application/octet-stream",
        uploaded_by=researcher_user.id
    )
    blob_gel = StorageBlob(
        file_name="t7_rnap_purification_sds_page.png",
        file_path="/storage/lims/gels/2026/t7_rnap_purification_sds_page.png",
        file_size_bytes=3410290,
        file_hash_sha256="c891ae58f019b23c923d8745ea987b201cdfe453a98762514bc910238f902ab1",
        format_category=FileFormatCategory.GEL_IMAGE_PNG.value,
        mime_type="image/png",
        uploaded_by=researcher_user.id
    )
    blob_nanodrop = StorageBlob(
        file_name="nanodrop_t7_rnap_sec_pool.csv",
        file_path="/storage/lims/spectroscopy/2026/nanodrop_t7_rnap_sec_pool.csv",
        file_size_bytes=4890,
        file_hash_sha256="e109d738f12a9bc4512e0987f4c01287eab4981290fd38e0192a54361094bc87",
        format_category=FileFormatCategory.NANODROP_CSV.value,
        mime_type="text/csv",
        uploaded_by=researcher_user.id
    )
    session.add_all([blob_histrap, blob_sec, blob_gel, blob_nanodrop])
    session.commit()

    # -------------------------------------------------------------------------
    # 5. Chromatography Columns
    # -------------------------------------------------------------------------
    col_histrap = FplcColumn(
        name="HisTrap HP 5 mL",
        column_type="affinity_ni_nta",
        bed_volume_ml=5.0,
        max_pressure_mpa=0.4,
        recommended_flow_rate_ml_min=5.0,
        serial_number="HTHP-5ML-89211",
        current_status="operational"
    )
    col_sec = FplcColumn(
        name="Superdex 200 Increase 10/300 GL",
        column_type="size_exclusion_sec",
        bed_volume_ml=24.0,
        max_pressure_mpa=1.8,
        recommended_flow_rate_ml_min=0.75,
        serial_number="SD200-INC-40294",
        current_status="operational"
    )
    session.add_all([col_histrap, col_sec])
    session.commit()

    # -------------------------------------------------------------------------
    # 6. BioSequence (T7 RNA Polymerase)
    # -------------------------------------------------------------------------
    t7_aa_seq = (
        "MGSSHHHHHHSSGLVPRGSHMLEMNTINIAKNDFSDIELAAIPFNTLADHYGERLAREQLALEHESYEMGEARFRKMFERQLKAGEVADNA"
        "AAKPLITTLLPKMIARINDWFEEVKAKRGKRPTAFQFLQEIKPEAVAYITIKTTLACLTSADNTTVQAVASAIGRAIEDEARFGRIRDLEAK"
        "HFKKNVEEQLNKRVGHVYKKAFMQVVEADMLSKGLLGGEAWSSWHKEDSIHVGVRCIEMLIESTGMVSLHRQNAGVVGQDSETIELAPEYAE"
        "AIATRAGALAGISPMFQPCVVPPKPWTGITGGGYWANGRRPLALVRTHSKKALMRYEDVYMPEVYKAINIAQNTAWKINKKVLAVANVITKW"
        "KHCPVEDIPAIEREELPMKPEDIDMNPEALTAWKRAAAAVYRKDKARKSRRISLEFMLEQANKFANHKAIWFPYNMDWRGRVYAVSMFNPQG"
        "NDMTKGLLTLAKGKPIGKEGYYWLKIHGANCAGVDKVPFPERIKFIEENHENIMACAKSPLENTWWAEQDSPFCFLAFCFEYAGVQHHGLSY"
        "NCSLPLAFDGSCSGIQHFSAMLRDEVGGRAVNLLPSETVQDIYGIVAKKVNEILQADAINGTDNEVVTVTDENTGEISEKVKLGTKALAGQW"
        "LAYGVTRSVTKRSVMTLAYGSKEFGFRQQVLEDTIQPAIDSGKGLMFTQPNQAAGYMAKLIWESVSVTVVAAVEAMNWLKSAAKLLAAEVKD"
        "KKTGEILRKRCAVHWVTPDGFPVWQEYKKPIQTRLNLMFLGQFRLQPTINTNKDSEIDAHKQESGIAPNFVHSQDGSHLRKTVVWAHEKYGI"
        "ESFALIHDSFGTIPADAANLFKAVRETMVDTYESCDVLADFYDQFADQLHESQLDKMPALPAKGNLNLRDILESDFAFA"
    )
    seq = BioSequence(
        name="pET-28a-T7RNAP",
        biomolecule_type=BiomoleculeType.RECOMBINANT_PROTEIN.value,
        sequence_data=t7_aa_seq,
        length_bp_or_aa=883,
        molecular_weight_da=98856.0,
        isoelectric_point_pi=6.24,
        extinction_coefficient_e280=140270.0,
        plasmid_map_json={
            "backbone": "pET-28a(+)",
            "promoter": "T7 lac",
            "tag": "N-terminal His6",
            "selection": "Kanamycin 50 ug/mL",
            "origin": "pBR322"
        },
        created_by=researcher_user.id
    )
    session.add(seq)
    session.commit()

    # -------------------------------------------------------------------------
    # 7. Experimental Campaign (5-Day Benchmark)
    # -------------------------------------------------------------------------
    campaign = ExperimentalCampaign(
        title="5-Day Recombinant T7 RNA Polymerase (pET-28a-T7RNAP) Expression & Dual-Column Purification",
        slug="t7-rnap-expression-2026",
        objective="Express and purify research-grade recombinant T7 RNA Polymerase (99 kDa) from 2 L BL21(DE3) culture to >95% purity for high-yield in vitro transcription (IVT) assays.",
        status=ExptStatus.COMPLETED.value,
        lead_user_id=researcher_user.id,
        sop_id=sop.id,
        started_at="2026-10-12T09:00:00Z",
        completed_at="2026-10-16T17:30:00Z",
        yield_mg_total=45.6,
        yield_percent_recovery=76.0,
        yield_mg_per_liter_culture=22.8,
        yield_ug_plasmid=120.0,
        yield_calculation_method="NanoDrop A280 (ext. coeff = 140,270 M-1 cm-1) on 16 mL Superdex 200 monomer pool (fractions B4-B8)",
        metadata_json={
            "host_strain": "BL21(DE3)",
            "culture_volume_l": 2.0,
            "wet_pellet_mass_g": 22.4,
            "final_purity_percent": 96.5,
            "storage_box_barcode": "BOX-PROT-T7RNAP-2026",
            "storage_slot": "C4"
        }
    )
    session.add(campaign)
    session.commit()

    # -------------------------------------------------------------------------
    # 8. Day 0: Transformation & Agar Plating
    # -------------------------------------------------------------------------
    entry_day0 = NotebookDailyEntry(
        campaign_id=campaign.id,
        day_number=0,
        entry_date="2026-10-12",
        title="Day 0: Transformation into BL21(DE3) & LB+Kan Agar Plating",
        summary="Thawed 50 uL chemically competent BL21(DE3) E. coli on ice. Added 100 ng pET-28a-T7RNAP plasmid DNA. Heat shocked at 42°C for 45 s, iced for 2 min. Added 900 uL SOC broth, recovered at 37°C 220 rpm for 60 min. Plated 100 uL onto LB + 50 ug/mL kanamycin agar plates. Incubated overnight at 37°C for 16 h.",
        protocol_deviations="None. Transformation efficiency optimal (~1.2 x 10^7 cfu/ug).",
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-12T18:00:00Z",
        yield_ug_plasmid=120.0,
        yield_calculation_method="NanoDrop A260 plasmid miniprep stock (340 ng/uL in TE)",
        operator_id=student_user.id
    )
    session.add(entry_day0)
    session.commit()

    pcr_day0 = PcrAssay(
        campaign_id=campaign.id,
        daily_entry_id=entry_day0.id,
        target_gene="T7RNAP_core",
        forward_primer_name="T7RNAP_Fwd_NdeI",
        forward_primer_seq="5'-CATATGACGAACATTAAAAAC-3'",
        reverse_primer_name="T7RNAP_Rev_XhoI",
        reverse_primer_seq="5'-CTCGAGTTACGCGAACGC-3'",
        annealing_temp_c=58.5,
        extension_time_sec=120,
        cycle_count=30,
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-12T16:30:00Z",
        yield_ug_plasmid=120.0,
        yield_calculation_method="Agarose 1% TAE gel quantification vs 1kb Plus DNA Ladder",
        notes="Colony PCR confirmed 2.65 kb expected amplicon from transformed BL21(DE3) clones."
    )
    session.add(pcr_day0)
    session.commit()

    # -------------------------------------------------------------------------
    # 9. Day 1: Starter Culture Inoculation & Overnight Growth
    # -------------------------------------------------------------------------
    entry_day1 = NotebookDailyEntry(
        campaign_id=campaign.id,
        day_number=1,
        entry_date="2026-10-13",
        title="Day 1: 50 mL Starter Culture Inoculation & Overnight Growth",
        summary="Inoculated single well-isolated BL21(DE3) colony from Day 0 plate into 50 mL sterile LB broth + 50 ug/mL kanamycin in a 250 mL baffled flask. Incubated in orbital shaker at 37°C, 220 rpm overnight for 16 h.",
        protocol_deviations="None.",
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-13T20:00:00Z",
        operator_id=student_user.id
    )
    session.add(entry_day1)
    session.commit()

    tp_d1_t0 = NotebookTimepointLog(
        entry_id=entry_day1.id,
        timepoint_label="t0_starter_inoculation",
        elapsed_minutes=0,
        temperature_c=37.0,
        od600=0.05,
        rpm=220,
        notes="Inoculated 50 mL LB+Kan flask with colony"
    )
    tp_d1_tf = NotebookTimepointLog(
        entry_id=entry_day1.id,
        timepoint_label="t_starter_overnight",
        elapsed_minutes=960,
        temperature_c=37.0,
        od600=3.20,
        rpm=220,
        notes="Dense starter culture ready for 2 L bioreactor/flask inoculation"
    )
    session.add_all([tp_d1_t0, tp_d1_tf])
    session.commit()

    # -------------------------------------------------------------------------
    # 10. Day 2: 2 L 2xYT Induction Kinetics & Overnight 20°C Expression
    # -------------------------------------------------------------------------
    entry_day2 = NotebookDailyEntry(
        campaign_id=campaign.id,
        day_number=2,
        entry_date="2026-10-14",
        title="Day 2: 2 L 2xYT Induction Kinetics & Overnight 20°C Expression",
        summary="Inoculated 2 x 1 L 2xYT broth + 50 ug/mL Kan with 2 x 20 mL Day 1 starter (1:50 dilution) in 2.8 L Fernbach flasks. Monitored OD600 at 37°C until OD600=0.68. Induced with 0.8 mM IPTG final concentration. Immediately shifted incubator temperature to 20°C for slow overnight expression (18 h). Final OD600 = 3.65.",
        protocol_deviations="None. Induction kinetics proceeded smoothly with robust biomass accumulation.",
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-14T23:59:00Z",
        operator_id=researcher_user.id
    )
    session.add(entry_day2)
    session.commit()

    # Induction timepoints: t0, +1h, +2h at OD600=0.68, overnight final OD600=3.65
    tp_d2_t0 = NotebookTimepointLog(
        entry_id=entry_day2.id,
        timepoint_label="t0_growth",
        elapsed_minutes=0,
        temperature_c=37.0,
        od600=0.08,
        rpm=220,
        notes="Inoculation of 2 L 2xYT media"
    )
    tp_d2_t1 = NotebookTimepointLog(
        entry_id=entry_day2.id,
        timepoint_label="t_growth_1h",
        elapsed_minutes=60,
        temperature_c=37.0,
        od600=0.22,
        rpm=220
    )
    tp_d2_t2 = NotebookTimepointLog(
        entry_id=entry_day2.id,
        timepoint_label="t_growth_2h",
        elapsed_minutes=120,
        temperature_c=37.0,
        od600=0.45,
        rpm=220
    )
    tp_d2_tind = NotebookTimepointLog(
        entry_id=entry_day2.id,
        timepoint_label="t_induction",
        elapsed_minutes=165,
        temperature_c=37.0,
        od600=0.68,
        rpm=220,
        notes="Target OD600=0.68 reached. Induced with 0.8 mM IPTG. Chilled incubator to 20°C."
    )
    tp_d2_p1 = NotebookTimepointLog(
        entry_id=entry_day2.id,
        timepoint_label="t_plus_1h",
        elapsed_minutes=225,
        temperature_c=20.0,
        od600=0.95,
        rpm=200,
        notes="1h post-induction, incubator stabilized at 20°C"
    )
    tp_d2_p2 = NotebookTimepointLog(
        entry_id=entry_day2.id,
        timepoint_label="t_plus_2h",
        elapsed_minutes=285,
        temperature_c=20.0,
        od600=1.48,
        rpm=200,
        notes="2h post-induction, robust recombinant expression underway"
    )
    tp_d2_harv = NotebookTimepointLog(
        entry_id=entry_day2.id,
        timepoint_label="t_overnight_harvest",
        elapsed_minutes=1245,
        temperature_c=20.0,
        od600=3.65,
        rpm=200,
        notes="18h overnight induction complete. Final OD600=3.65. Ready for cell harvest."
    )
    session.add_all([tp_d2_t0, tp_d2_t1, tp_d2_t2, tp_d2_tind, tp_d2_p1, tp_d2_p2, tp_d2_harv])
    session.commit()

    # -------------------------------------------------------------------------
    # 11. Day 3: Harvest (22.4 g Wet Pellet), Sonication & HisTrap HP Ni-NTA FPLC
    # -------------------------------------------------------------------------
    entry_day3 = NotebookDailyEntry(
        campaign_id=campaign.id,
        day_number=3,
        entry_date="2026-10-15",
        title="Day 3: Harvest (22.4 g Wet Pellet), Benzonase Sonication Lysis & HisTrap HP 5 mL Ni-NTA FPLC",
        summary="Centrifuged 2 L culture at 4,000 x g for 25 min at 4°C, obtaining 22.4 g wet cell pellet. Resuspended pellet in 100 mL Lysis Buffer containing 25 U/mL Benzonase and 1 mM PMSF. Lyzed via sonication on ice (10 cycles: 30s pulse, 45s rest, 65% amplitude). Clarified lysate at 18,000 x g for 45 min at 4°C. Loaded clarified supernatant onto HisTrap HP 5 mL column at 4.0 mL/min. Washed with 15 CV 50 mM imidazole wash buffer. Eluted with 10 CV 50-500 mM imidazole linear gradient. Pooled peak fractions E3-E7 (30 mL, ~60 mg protein).",
        protocol_deviations="None.",
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-15T18:30:00Z",
        yield_mg_total=60.0,
        yield_percent_recovery=85.0,
        yield_mg_per_liter_culture=30.0,
        yield_calculation_method="A280 absorbance of pooled Ni-NTA elution fractions (30 mL at 2.0 mg/mL)",
        operator_id=researcher_user.id
    )
    session.add(entry_day3)
    session.commit()

    run_histrap = FplcRun(
        campaign_id=campaign.id,
        daily_entry_id=entry_day3.id,
        column_id=col_histrap.id,
        run_name="T7RNAP_Capture_HisTrap_5mL_Run01",
        purification_step="capture_ni_nta",
        flow_rate_ml_min=4.0,
        buffer_a="50 mM Tris-HCl pH 8.0, 300 mM NaCl, 20 mM imidazole, 5% glycerol, 1 mM DTT",
        buffer_b="50 mM Tris-HCl pH 8.0, 300 mM NaCl, 500 mM imidazole, 5% glycerol, 1 mM DTT",
        gradient_profile_json={
            "equilibration_cv": 5.0,
            "sample_load_ml": 100.0,
            "wash_step_cv": 15.0,
            "elution_gradient_cv": 10.0,
            "strip_cv": 5.0
        },
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-15T17:00:00Z",
        yield_mg_total=60.0,
        yield_percent_recovery=85.0,
        yield_mg_per_liter_culture=30.0,
        yield_calculation_method="A280 measurement of pooled elution peak E3-E7",
        raw_data_blob_id=blob_histrap.id,
        chromatogram_summary_json={
            "peak_apex_retention_ml": 42.5,
            "peak_apex_uv280_mau": 2840.2,
            "pooled_fractions": ["E3", "E4", "E5", "E6", "E7"]
        }
    )
    session.add(run_histrap)
    session.commit()

    # Fractions for Ni-NTA Run
    histrap_fraction_data = [
        ("E1", 20.0, 45.2, 18.1, False, "Early wash tail"),
        ("E2", 25.0, 120.4, 42.0, False, "Leading shoulder"),
        ("E3", 30.0, 890.5, 210.0, True, "Main peak start - pooled"),
        ("E4", 35.0, 2150.0, 480.0, True, "Main peak ascending - pooled"),
        ("E5", 40.0, 2840.2, 620.0, True, "Main peak apex - pooled"),
        ("E6", 45.0, 1980.6, 430.0, True, "Main peak descending - pooled"),
        ("E7", 50.0, 750.1, 180.0, True, "Main peak tail - pooled"),
        ("E8", 55.0, 180.3, 50.0, False, "Post-peak baseline return"),
        ("E9", 60.0, 65.0, 20.0, False, "High imidazole strip"),
        ("E10", 65.0, 25.1, 10.0, False, "Column re-equilibration")
    ]
    for frac_num, ret_vol, uv280, uv260, pooled, notes in histrap_fraction_data:
        frac = FplcFraction(
            run_id=run_histrap.id,
            fraction_number=frac_num,
            retention_volume_ml=ret_vol,
            uv280_mau=uv280,
            uv260_mau=uv260,
            conductivity_ms_cm=35.4,
            is_pooled=pooled,
            notes=notes
        )
        session.add(frac)
    session.commit()

    # -------------------------------------------------------------------------
    # 12. Day 4: Superdex 200 SEC Polishing, Monomer Pooling (B4-B8), SDS-PAGE & NanoDrop
    # -------------------------------------------------------------------------
    entry_day4 = NotebookDailyEntry(
        campaign_id=campaign.id,
        day_number=4,
        entry_date="2026-10-16",
        title="Day 4: Superdex 200 SEC Polishing, Monomer Peak Pooling (B4-B8), SDS-PAGE & NanoDrop Quant",
        summary="Concentrated Ni-NTA pool to 3.0 mL (Amicon 30 kDa MWCO). Injected onto Superdex 200 Increase 10/300 GL column in Storage SEC Buffer at 0.75 mL/min. Symmetric monodisperse monomer peak eluted cleanly at 12.8 mL (fractions B4-B8, 16 mL total). 4-20% SDS-PAGE gel confirmed >95% purity (96.5% by densitometry) single band at 99 kDa. NanoDrop quantified: A280=4.02, A260=2.29, A260/A280=0.57, concentration=2.85 mg/mL. Final total yield 45.6 mg (22.8 mg/L culture, 76% overall recovery). Aliquoted 16 x 1 mL vials into Freezer Box PROT-2026-T7RNAP slot C4 at -80°C.",
        protocol_deviations="None. Monodisperse SEC profile with no high-molecular-weight aggregate void peak.",
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-16T17:30:00Z",
        yield_mg_total=45.6,
        yield_percent_recovery=76.0,
        yield_mg_per_liter_culture=22.8,
        yield_ug_plasmid=120.0,
        yield_calculation_method="NanoDrop A280 (A280=4.02, ext. coeff=140,270 M-1 cm-1, 16 mL monomer pool)",
        operator_id=researcher_user.id
    )
    session.add(entry_day4)
    session.commit()

    run_sec = FplcRun(
        campaign_id=campaign.id,
        daily_entry_id=entry_day4.id,
        column_id=col_sec.id,
        run_name="T7RNAP_Polishing_Superdex200_Run02",
        purification_step="polishing_sec",
        flow_rate_ml_min=0.75,
        buffer_a="50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM EDTA, 1 mM DTT, 50% glycerol",
        gradient_profile_json={
            "isocratic_volume_ml": 30.0,
            "sample_volume_ml": 3.0
        },
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-16T14:45:00Z",
        yield_mg_total=45.6,
        yield_percent_recovery=76.0,
        yield_mg_per_liter_culture=22.8,
        yield_calculation_method="A280 of pooled fractions B4-B8 (16 mL at 2.85 mg/mL)",
        raw_data_blob_id=blob_sec.id,
        chromatogram_summary_json={
            "void_volume_ml": 8.8,
            "monomer_apex_ml": 12.8,
            "monomer_apex_uv280_mau": 2450.8,
            "pooled_fractions": ["B4", "B5", "B6", "B7", "B8"],
            "pool_volume_ml": 16.0
        }
    )
    session.add(run_sec)
    session.commit()

    sec_fractions_data = [
        ("B1", 9.0, 15.2, 8.1, False, "Void volume exclusion - negligible aggregate"),
        ("B2", 10.0, 22.1, 11.0, False, "Pre-peak baseline"),
        ("B3", 11.0, 85.0, 42.0, False, "Leading shoulder"),
        ("B4", 11.8, 640.2, 345.0, True, "Monomer peak start (pooled)"),
        ("B5", 12.4, 1820.5, 980.0, True, "Monomer ascending (pooled)"),
        ("B6", 12.8, 2450.8, 1320.0, True, "Monomer peak apex 99 kDa (pooled)"),
        ("B7", 13.4, 1740.1, 930.0, True, "Monomer descending (pooled)"),
        ("B8", 14.0, 580.4, 310.0, True, "Monomer tail (pooled)"),
        ("B9", 14.8, 110.2, 60.0, False, "Trailing baseline"),
        ("B10", 15.6, 45.0, 25.0, False, "Post-peak"),
        ("B11", 16.5, 20.1, 12.0, False, "Small molecule salt boundary"),
        ("B12", 18.0, 12.0, 7.0, False, "Total column volume exit")
    ]
    for frac_num, ret_vol, uv280, uv260, pooled, notes in sec_fractions_data:
        frac = FplcFraction(
            run_id=run_sec.id,
            fraction_number=frac_num,
            retention_volume_ml=ret_vol,
            uv280_mau=uv280,
            uv260_mau=uv260,
            conductivity_ms_cm=14.2,
            is_pooled=pooled,
            notes=notes
        )
        session.add(frac)
    session.commit()

    # -------------------------------------------------------------------------
    # 13. SDS-PAGE Gel Record & Lanes
    # -------------------------------------------------------------------------
    gel = GelRecord(
        campaign_id=campaign.id,
        daily_entry_id=entry_day4.id,
        gel_type="SDS-PAGE 4-20% Tris-Glycine",
        voltage_v=180,
        run_time_minutes=45,
        staining_method="Coomassie Brilliant Blue R-250",
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-16T16:00:00Z",
        image_blob_id=blob_gel.id,
        purity_assessment_percent=96.5,
        notes="Densitometric analysis of Lane 8 demonstrates 96.5% purity (>95% QC requirement met) with distinct 99 kDa T7 RNAP band."
    )
    session.add(gel)
    session.commit()

    lanes_data = [
        (1, "Precision Plus Protein Unstained Standards", "ladder", 5.0, 99.0, 500.0, 100.0, "Bio-Rad ladder 10-250 kDa"),
        (2, "Total Cell Lysate (post-sonication)", "total_lysate", 15.0, 99.0, 1500.0, 24.5, "Strong induced T7 RNAP band visible"),
        (3, "Clarified Soluble Supernatant", "soluble_fraction", 15.0, 99.0, 1200.0, 38.0, "T7 RNAP highly soluble"),
        (4, "Insoluble Pellet Resuspension", "insoluble_pellet", 15.0, 99.0, 300.0, 8.5, "Minor inclusion body fraction"),
        (5, "HisTrap Ni-NTA Flowthrough", "flowthrough", 15.0, 99.0, 50.0, 3.2, "Complete capture; negligible uncaptured RNAP"),
        (6, "HisTrap 50 mM Imidazole Wash", "wash", 15.0, 99.0, 180.0, 12.0, "Removal of non-specific host proteins"),
        (7, "HisTrap Elution Pool (Fractions E3-E7)", "elution_pool", 10.0, 99.0, 2000.0, 88.5, "Enriched T7 RNAP ~88.5% purity"),
        (8, "Superdex 200 Monomer Pool (Fractions B4-B8)", "sec_monomer_peak", 5.0, 99.0, 1425.0, 96.5, "Single sharp 99 kDa monomer band >95% purity")
    ]
    for lane_no, s_name, s_type, vol, mw, mass, purity, notes in lanes_data:
        lane = GelLane(
            gel_id=gel.id,
            lane_number=lane_no,
            sample_name=s_name,
            sample_type=s_type,
            volume_loaded_ul=vol,
            estimated_mw_kda=mw,
            estimated_mass_ng=mass,
            purity_percentage=purity,
            band_analysis_json={"rf_value": 0.42, "mw_kda": mw, "purity_pct": purity},
            notes=notes
        )
        session.add(lane)
    session.commit()

    # -------------------------------------------------------------------------
    # 14. NanoDrop Quantification Measurement
    # -------------------------------------------------------------------------
    nanodrop = NanodropMeasurement(
        campaign_id=campaign.id,
        daily_entry_id=entry_day4.id,
        sample_name="T7_RNAP_Superdex200_Pool_B4-B8",
        biomolecule_type=BiomoleculeType.RECOMBINANT_PROTEIN.value,
        concentration_mg_per_ml=2.85,
        a280=4.02,
        a260=2.29,
        a260_a280_ratio=0.57,
        a260_a230_ratio=2.15,
        buffer_blank="50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM EDTA, 1 mM DTT, 50% glycerol",
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-16T16:30:00Z",
        yield_mg_total=45.6,
        yield_percent_recovery=76.0,
        yield_mg_per_liter_culture=22.8,
        yield_ug_plasmid=120.0,
        yield_calculation_method="Beer-Lambert: conc = A280 / (e * l) = 4.02 / 1.41 = 2.85 mg/mL; Total = 2.85 mg/mL * 16.0 mL = 45.6 mg",
        raw_blob_id=blob_nanodrop.id
    )
    session.add(nanodrop)
    session.commit()

    # -------------------------------------------------------------------------
    # 15. Final LIMS Inventory Tube in Freezer Box Slot C4
    # -------------------------------------------------------------------------
    tube = InventoryTube(
        box_id=box.id,
        box_position="C4",
        barcode="TUBE-T7RNAP-2026-004",
        sample_name="T7 RNA Polymerase (Recombinant, >95% pure, 2.85 mg/mL)",
        biomolecule_type=BiomoleculeType.RECOMBINANT_PROTEIN.value,
        concentration_mg_ml=2.85,
        volume_ul=1000.0,
        buffer_composition="50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM EDTA, 1 mM DTT, 50% (v/v) glycerol",
        campaign_id=campaign.id,
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-16T17:00:00Z",
        yield_mg_total=45.6,
        yield_percent_recovery=76.0,
        yield_mg_per_liter_culture=22.8,
        yield_ug_plasmid=120.0,
        yield_calculation_method="NanoDrop A280 on Superdex 200 SEC Monomer Pool B4-B8 (16 mL total pool, 16 aliquots)",
        metadata_json={
            "storage_temp_c": -80.0,
            "specific_activity_u_per_mg": 125000,
            "freeze_thaw_cycles": 0,
            "purity_pct": 96.5,
            "sec_fractions": "B4-B8"
        }
    )
    session.add(tube)
    session.commit()

    # -------------------------------------------------------------------------
    # 16. Computational Pipeline & Assay Records
    # -------------------------------------------------------------------------
    code_run = CodeAnalysisRun(
        campaign_id=campaign.id,
        tool_name="BioLabCalc IVT Yield & Extinction Coefficient Analysis",
        script_path="scripts/ivt_yield_kinetics.py",
        git_commit_hash="a8f3b41d0e82c59",
        parameters_json={
            "mw_da": 98856.0,
            "extinction_coeff_e280": 140270.0,
            "pool_volume_ml": 16.0,
            "a280_reading": 4.02
        },
        results_json={
            "calculated_yield_mg": 45.6,
            "recovery_percent": 76.0,
            "mg_per_liter_culture": 22.8,
            "passed_qc": True
        },
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-16T17:15:00Z"
    )
    session.add(code_run)
    session.commit()

    # Optional patch recording for electrophysiology table completeness
    ephys = EphysRecording(
        campaign_id=campaign.id,
        cell_type="HEK293T",
        patch_configuration="whole_cell",
        bath_solution="140 mM NaCl, 4 mM KCl, 2 mM CaCl2, 1 mM MgCl2, 10 mM HEPES, 10 mM Glucose pH 7.4",
        pipette_solution="130 mM K-gluconate, 10 mM KCl, 10 mM HEPES, 1 mM EGTA, 2 mM Mg-ATP pH 7.2",
        holding_potential_mv=-70.0,
        sampling_rate_khz=20.0,
        status=ExptStatus.COMPLETED.value,
        completed_at="2026-10-16T17:20:00Z",
        summary_metrics_json={"input_resistance_mohm": 420.5, "series_resistance_mohm": 12.3}
    )
    session.add(ephys)
    session.commit()

    # -------------------------------------------------------------------------
    # 17. Multi-Modal RAG Document Chunks (5 Semantically Rich Chunks)
    # -------------------------------------------------------------------------
    chunks_text = [
        (
            "campaign",
            campaign.id,
            0,
            "Campaign Overview: 5-Day Recombinant T7 RNA Polymerase (pET-28a-T7RNAP) Expression & Dual-Column Purification. Achieved 45.6 mg total yield (22.8 mg/L culture, 76% recovery) from 2 L BL21(DE3) culture. Verified >95% purity (96.5% SDS-PAGE) at 99 kDa. Stored in Box PROT-2026-T7RNAP slot C4.",
            "campaign:t7-rnap-expression-2026:summary",
            1.1
        ),
        (
            "sop",
            sop.id,
            1,
            "SOP-PROT-T7RNAP-01 Protocol: Recombinant T7 RNA Polymerase Purification using HisTrap HP 5 mL Ni-NTA and Superdex 200 Increase 10/300 GL SEC. Lysis with Benzonase, 50 mM imidazole wash, 50-500 mM gradient elution. Storage in 50% glycerol at -80°C.",
            "sop:SOP-PROT-T7RNAP-01:protocol",
            2.3
        ),
        (
            "daily_entry",
            entry_day2.id,
            2,
            "Day 2 T7 RNAP Induction Kinetics: 2 L 2xYT culture grown to OD600=0.68 at 37°C, then induced with 0.8 mM IPTG for T7 RNA Polymerase expression. Shifted to 20°C for 18h overnight expression. Final harvest OD600 reached 3.65.",
            "daily_entry:day2:induction_kinetics",
            3.7
        ),
        (
            "daily_entry",
            entry_day3.id,
            3,
            "Day 3 Harvest & Capture: Centrifuged 2 L culture yielding 22.4 g wet cell pellet. Probe sonication with Benzonase. HisTrap HP 5 mL Ni-NTA capture yielded 60.0 mg intermediate T7 RNAP protein in 30 mL pool.",
            "daily_entry:day3:histrap_capture",
            4.9
        ),
        (
            "daily_entry",
            entry_day4.id,
            4,
            "Day 4 SEC Polishing & Final QC: Superdex 200 Increase 10/300 GL monomer peak pooling (fractions B4-B8, 16 mL). NanoDrop A280=4.02 (2.85 mg/mL, 45.6 mg yield). SDS-PAGE confirmed 96.5% purity at 99 kDa. Archived in tube TUBE-T7RNAP-2026-004 at slot C4.",
            "daily_entry:day4:sec_polishing_qc",
            5.8
        )
    ]

    for entity_type, entity_id, c_idx, text, prov, seed_val in chunks_text:
        emb = _generate_synthetic_embedding(seed_val, dim=1536)
        chunk = RagDocumentChunk(
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            chunk_index=c_idx,
            chunk_text=text,
            lexical_tsvector=text.lower(),
            extracted_metadata={
                "campaign_slug": "t7-rnap-expression-2026",
                "biomolecule": "T7 RNA Polymerase",
                "yield_mg_total": 45.6
            },
            provenance_context=prov,
            embedding=emb
        )
        session.add(chunk)
    session.commit()

    # -------------------------------------------------------------------------
    # 18. Audit Log Tracking Campaign Lifecycle
    # -------------------------------------------------------------------------
    audit = AuditLog(
        user_id=researcher_user.id,
        action="CAMPAIGN_COMPLETED",
        entity_type="experimental_campaigns",
        entity_id=campaign.id,
        changes={
            "status": {"old": "in_progress", "new": "completed"},
            "yield_mg_total": 45.6,
            "yield_percent_recovery": 76.0,
            "storage_position": "BOX-PROT-T7RNAP-2026:C4"
        },
        client_ip="192.168.1.104"
    )
    session.add(audit)
    session.commit()

    return {
        "campaign_id": campaign.id,
        "box_id": box.id,
        "tube_id": tube.id,
        "sop_id": sop.id,
        "col_histrap_id": col_histrap.id,
        "col_sec_id": col_sec.id,
        "gel_id": gel.id,
        "nanodrop_id": nanodrop.id,
        "lead_user_id": researcher_user.id
    }
