"""Comprehensive wet-lab molecular biology and biochemistry protocols.

Provides standardized, battle-tested step-by-step laboratory procedures with
reagent formulations, incubation parameters, bench safety notes, and troubleshooting matrices.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass(frozen=True)
class ProtocolReagent:
    name: str
    concentration: str
    amount_or_volume: str
    notes: str = ""


@dataclass(frozen=True)
class ProtocolStep:
    step_number: int
    title: str
    instruction: str
    temperature: Optional[str] = None
    duration: Optional[str] = None
    tip: Optional[str] = None


@dataclass(frozen=True)
class TroubleshootingItem:
    issue: str
    possible_cause: str
    solution: str


@dataclass(frozen=True)
class LabProtocol:
    protocol_id: str
    title: str
    category: str
    summary: str
    estimated_time: str
    skill_level: str
    safety_notes: List[str]
    reagents: List[ProtocolReagent]
    materials_equipment: List[str]
    steps: List[ProtocolStep]
    troubleshooting: List[TroubleshootingItem]
    references: List[str] = field(default_factory=list)


PROTOCOL_CATALOG: Dict[str, LabProtocol] = {
    "ntp_neutralization": LabProtocol(
        protocol_id="ntp_neutralization",
        title="25 mM Neutralized NTP Mix Preparation (pH 7.5)",
        category="Solutions & Reagents",
        summary="Preparation and pH neutralization of ribonucleotide triphosphate (ATP, CTP, GTP, UTP) stocks from acidic salts for high-efficiency in vitro transcription.",
        estimated_time="30–45 minutes",
        skill_level="Intermediate",
        safety_notes=[
            "5 M NaOH is highly corrosive and causes severe skin burns and eye damage. Handle with eye protection in a fume hood or bench shield.",
            "Use RNase-free certified reagents, tips, and tubes to prevent hydrolytic degradation of ribonucleotides.",
            "Avoid warming NTP solutions above room temperature; store on ice during preparation."
        ],
        reagents=[
            ProtocolReagent("100 mM NTP Stocks (ATP, CTP, GTP, UTP)", "100 mM each", "1.0 mL each (4.0 mL total)", "Disodium salt or free acid"),
            ProtocolReagent("5.0 M Sodium Hydroxide (NaOH)", "5.0 M", "~110 µL (titrated)", "Freshly prepared to avoid carbonation"),
            ProtocolReagent("1.0 M / 0.5 M NaOH", "0.5 M or 1.0 M", "~50–100 µL", "For precision dropwise pH fine-tuning"),
            ProtocolReagent("Nuclease-Free Water (ddH2O)", "Molecular biology grade", "QS to 16.0 mL (~11.9 mL)", "Autoclaved DEPC-treated or 0.1 µm filtered"),
        ],
        materials_equipment=[
            "Calibrated micro-pH electrode (or narrow-range pH 6.0–8.0 test strips)",
            "Standard pH calibration buffers (pH 4.01, 7.00, 10.01)",
            "P1000, P200, and P10 micropipettes with sterile RNase-free filter tips",
            "15 mL or 50 mL sterile conical polypropylene tube",
            "Magnetic micro-stirrer and stir bar (optional but recommended)",
            "Sterile 1.5 mL low-binding microcentrifuge tubes for aliquoting",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Reagent Thawing & Inspection",
                instruction="Thaw individual 100 mM NTP stocks on ice. Invert to mix thoroughly and pulse-spin. Inspect vendor documentation to confirm whether the stock is already pre-neutralized (pH 7.0–7.5). If already pre-neutralized, DO NOT add NaOH; simply dilute with water.",
                temperature="4°C (on ice)",
                duration="10 min",
                tip="Commercial pre-neutralized NTPs will turn severely alkaline (pH > 10) if base is added!"
            ),
            ProtocolStep(
                step_number=2,
                title="Combine Nucleotide Stocks",
                instruction="Combine 1.0 mL each of 100 mM ATP, 100 mM CTP, 100 mM GTP, and 100 mM UTP into a clean 15 mL tube to yield 4.0 mL of equimolar NTP mix (100 mM total, or 25 mM each).",
                temperature="20–25°C",
                duration="2 min",
                tip="Check that no precipitate is present. GTP can precipitate at cold temperatures; warm gently with hands if cloudy."
            ),
            ProtocolStep(
                step_number=3,
                title="Initial Diluent Addition",
                instruction="Add 8.0 mL to 9.0 mL of nuclease-free water to the tube. DO NOT add the full 12.0 mL of water upfront, as adding base during titration will cause the volume to exceed the 16.0 mL mark.",
                temperature="20–25°C",
                duration="1 min",
                tip="Always leave 2–3 mL of volume headroom for titrant addition."
            ),
            ProtocolStep(
                step_number=4,
                title="Coarse Neutralization",
                instruction="Calibrate the pH electrode with pH 4.0, 7.0, and 10.0 standards. For 400 µmol total NTPs starting from disodium salt, add ~85 µL of 5 M NaOH (~80% of theoretical requirement) while stirring gently.",
                temperature="20–25°C",
                duration="3 min",
                tip="Adding 80% first prevents overshooting the steep portion of the titration curve near pH 7.5."
            ),
            ProtocolStep(
                step_number=5,
                title="Fine pH Adjustment to 7.5",
                instruction="Insert the micro-pH electrode. Slowly add 0.5 M or 1.0 M NaOH in 1–2 µL increments with gentle vortexing or stirring until the pH stabilizes at 7.50 ± 0.05. If pH overshoots slightly, back-titrate with 0.1 M HCl.",
                temperature="20–25°C",
                duration="10 min",
                tip="CTP is sensitive to deamination to UTP at pH > 8.5; do not let pH drift above 8.0."
            ),
            ProtocolStep(
                step_number=6,
                title="Bring to Final Volume (QS)",
                instruction="Transfer the solution to a calibrated 25 mL graduated cylinder or volumetric tube. Bring the final volume to exactly 16.0 mL with nuclease-free water. Invert 10 times to ensure homogeneity.",
                temperature="20–25°C",
                duration="3 min",
                tip="The resulting solution contains 25.0 mM total NTP (6.25 mM each ATP, CTP, GTP, UTP), or 25 mM each if prepared from individual 100 mM single stocks."
            ),
            ProtocolStep(
                step_number=7,
                title="Aliquoting & Flash Freezing",
                instruction="Aliquot the neutralized 25 mM NTP solution into single-use 100 µL or 500 µL aliquots in RNase-free 1.5 mL tubes. Label with concentration, pH 7.5, and date. Store immediately at -20°C or -80°C.",
                temperature="-20°C or -80°C",
                duration="5 min",
                tip="Repeated freeze-thaw cycles (>5) degrade ribonucleotide triphosphate linkages into diphosphates and monophosphates."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="pH overshoots past 8.2 during NaOH addition",
                possible_cause="Buffer capacity decreases rapidly past pH 7.0 (pKa of gamma-phosphate is ~6.65).",
                solution="Immediately add 1.0 M HCl in 1 µL increments under micro-probe measurement until pH returns to 7.50."
            ),
            TroubleshootingItem(
                issue="Final volume exceeds 16.0 mL before reaching pH 7.5",
                possible_cause="All 12.0 mL of water was added before starting titration, or too dilute NaOH (<0.5 M) was used.",
                solution="Always reserve 2–3 mL of the diluent budget for titrant. If volume is exceeded, recalculate the true final concentration (C2 = 400 µmol / V_actual) and adjust downstream reaction pipetting."
            ),
            TroubleshootingItem(
                issue="White precipitate observed after freezing/thawing",
                possible_cause="GTP sodium salt has lower solubility at low temperatures and high ionic strength.",
                solution="Incubate at 37°C for 3–5 minutes and vortex vigorously; GTP will re-dissolve completely into clear solution."
            )
        ],
        references=[
            "Milligan, J. F., & Uhlenbeck, O. C. (1989). Synthesis of small RNAs using T7 RNA polymerase. Methods in Enzymology, 180, 51-62.",
            "Sambrook, J., & Russell, D. W. (2001). Molecular Cloning: A Laboratory Manual. Cold Spring Harbor Laboratory Press."
        ]
    ),

    "t7_ivt_transcription": LabProtocol(
        protocol_id="t7_ivt_transcription",
        title="High-Yield T7 In Vitro Transcription (IVT) of RNA",
        category="RNA Biochemistry",
        summary="Enzymatic synthesis of single-stranded RNA from DNA templates (linearized plasmid or PCR amplicon) harboring a T7 promoter sequence (5'-TAATACGACTCACTATA-3').",
        estimated_time="2.5–4.5 hours",
        skill_level="Intermediate",
        safety_notes=[
            "Decontaminate pipettes, benches, and gloves with RNaseZap or 0.1 M NaOH to prevent degradation by ubiquitous environmental RNases.",
            "Avoid aerosol formation during pipetting; always use certified RNase-free aerosol-barrier filter tips."
        ],
        reagents=[
            ProtocolReagent("10X T7 Transcription Buffer", "10X", "2.0 µL (for 20 µL rxn)", "400 mM Tris-HCl pH 7.9, 100 mM DTT, 20 mM Spermidine"),
            ProtocolReagent("Neutralized NTP Mix (pH 7.5)", "25 mM each NTP", "4.0 µL", "Final: 5.0 mM each NTP in reaction"),
            ProtocolReagent("Magnesium Chloride (MgCl2)", "100 mM stock", "4.0 µL", "Final: 20 mM MgCl2 (optimal Mg:NTP ratio is 1:1)"),
            ProtocolReagent("Linearized Template DNA / PCR Product", "100–500 ng/µL", "1.0–2.0 µg", "Clean, phenol-chloroform or column purified"),
            ProtocolReagent("Murine RNase Inhibitor", "40 U/µL", "0.5 µL (20 Units)", "Protects nascent RNA from ribonucleases"),
            ProtocolReagent("Yeast Inorganic Pyrophosphatase (IPP)", "0.1 U/µL", "0.5 µL (0.05 Units)", "Hydrolyzes PPi precipitate and boosts yields"),
            ProtocolReagent("T7 RNA Polymerase", "20–50 U/µL", "1.0 µL", "Homebrew or commercial recombinant enzyme"),
            ProtocolReagent("Nuclease-Free Water", "Molecular grade", "QS to 20.0 µL", "-"),
            ProtocolReagent("DNase I (RNase-free)", "2 U/µL", "1.0 µL", "For post-transcriptional template degradation"),
        ],
        materials_equipment=[
            "PCR thermal cycler or 37°C dry incubator heat block",
            "Aerosol-barrier RNase-free filter pipette tips",
            "0.2 mL thin-walled PCR strip tubes or 1.5 mL microcentrifuge tubes",
            "NanoDrop spectrophotometer or Qubit fluorometer for RNA yield measurement",
            "Agarose or Urea-PAGE electrophoresis apparatus for transcript integrity verification",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Reaction Assembly on Bench",
                instruction="Thaw reaction components on ice, except 10X Transcription Buffer (thaw at RT to dissolve spermidine-spermidine precipitates). Assemble reaction in a sterile 0.2 mL PCR tube in the following order: Water -> 10X Buffer -> NTPs -> MgCl2 -> Template DNA -> RNase Inhibitor -> IPP -> T7 RNA Polymerase.",
                temperature="20–25°C",
                duration="5 min",
                tip="Always add 10X buffer and water BEFORE template and polymerase to prevent spermidine from precipitating the DNA template!"
            ),
            ProtocolStep(
                step_number=2,
                title="Mix & Incubation",
                instruction="Pipette gently up and down 5 times to mix; do not vortex vigorously to avoid denaturing T7 RNA polymerase. Spin briefly in a microcentrifuge. Incubate at 37°C for 2 to 4 hours in a thermal cycler with heated lid (set to 50°C).",
                temperature="37°C",
                duration="2–4 hours",
                tip="For short transcripts (<50 nt) or aptamers, incubation at 37°C for 3–4 hours or 42°C for 2 hours improves yield."
            ),
            ProtocolStep(
                step_number=3,
                title="Template DNA Degradation",
                instruction="Add 1.0 µL of RNase-free DNase I (2 U/µL) directly to the transcription reaction. Mix gently and incubate at 37°C for 15 minutes.",
                temperature="37°C",
                duration="15 min",
                tip="DNase I digest eliminates template DNA, ensuring downstream UV A260 readings measure synthesized RNA only."
            ),
            ProtocolStep(
                step_number=4,
                title="Reaction Quenching & Cleanup",
                instruction="Stop the reaction by adding 2.0 µL of 0.2 M EDTA (pH 8.0) or proceed immediately to silica spin column purification (e.g. Monarch/Zymo RNA Clean & Concentrator) or ethanol precipitation.",
                temperature="20–25°C",
                duration="5 min",
                tip="EDTA chelates Mg2+, preventing spontaneous non-enzymatic RNA cleavage during handling."
            ),
            ProtocolStep(
                step_number=5,
                title="Quantification & Quality Assessment",
                instruction="Measure A260 absorbance on the NanoDrop (using 1X TE as blank). Calculate concentration using the sequence-specific extinction coefficient or general 40 µg/mL/AU rule. Run 200 ng on a 2% agarose or denaturing urea gel to verify clean single-band synthesis.",
                temperature="20–25°C",
                duration="10 min",
                tip="A typical 20 µL reaction produces 30–80 µg of purified RNA (1.5–4.0 mg/mL yield)."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="Low or no RNA yield",
                possible_cause="Template DNA contains ethanol or phenol residue, incomplete linear digestion, or degraded NTPs.",
                solution="Gel-purify or ethanol-precipitate template DNA prior to IVT. Ensure template has a full T7 promoter sequence (TAATACGACTCACTATAGGG)."
            ),
            TroubleshootingItem(
                issue="White cloudy precipitate in reaction tube during incubation",
                possible_cause="Inorganic magnesium pyrophosphate (Mg2P2O7) precipitation, typical in high-yield reactions.",
                solution="Add 0.05 U of inorganic pyrophosphatase (IPP); it hydrolyzes PPi into soluble monophosphate and prevents Mg2+ depletion."
            ),
            TroubleshootingItem(
                issue="Smearing or multiple low-molecular-weight bands on gel",
                possible_cause="RNase contamination or abortive transcription cycling.",
                solution="Use fresh RNase inhibitor. Increase GTP concentration to 6 mM for initiation if the transcript starts with GGG."
            )
        ],
        references=[
            "Beckert, B., & Masquida, B. (2011). Synthesis of RNA by in vitro transcription. Methods in Molecular Biology, 703, 29-41.",
            "Rio, D. C. (2014). In vitro transcription using T7 RNA polymerase. Cold Spring Harbor Protocols, 2014(9), pdb-prot080887."
        ]
    ),

    "ecoli_transformation": LabProtocol(
        protocol_id="ecoli_transformation",
        title="Heat-Shock Transformation of Chemically Competent E. coli",
        category="Microbiology & Culture",
        summary="High-efficiency uptake of plasmid DNA or recombinant ligation/Gibson assembly products into chemically competent E. coli cells (DH5alpha, TOP10, BL21).",
        estimated_time="1.5 hours",
        skill_level="Beginner",
        safety_notes=[
            "E. coli is a Biosafety Level 1 (BSL-1) organism. Follow standard aseptic microbiological technique.",
            "Decontaminate all bacterial wastes with 10% bleach (min 20 min contact time) or autoclave at 121°C."
        ],
        reagents=[
            ProtocolReagent("Chemically Competent E. coli Cells", "High competency (>= 1e8 cfu/µg)", "50 µL per reaction", "Thaw strictly on wet ice"),
            ProtocolReagent("Plasmid DNA or Assembly Product", "10 pg to 100 ng", "1.0–3.0 µL", "Do not exceed 10% of cell volume"),
            ProtocolReagent("SOC Medium (or 2xYT / LB)", "Room temp or 37°C", "950 µL", "SOC provides glucose for rapid cell recovery"),
            ProtocolReagent("Selective LB Agar Plates", "Standard", "1–2 plates per rxn", "Containing appropriate antibiotic (Amp, Kan, Cam)"),
        ],
        materials_equipment=[
            "Floating tube rack and wet ice bucket",
            "Precision water bath or calibrated heat block set to exactly 42°C",
            "Shaking incubator set to 37°C (225–250 rpm)",
            "Sterile cell spreaders or glass beads",
            "37°C static agar plate incubator",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Cell Thawing on Ice",
                instruction="Retrieve competent cell aliquots from -80°C freezer and place immediately in wet ice. Allow to thaw slowly for ~10 minutes. Pre-warm SOC medium to room temperature or 37°C and pre-warm selective agar plates in 37°C incubator.",
                temperature="0°C (wet ice)",
                duration="10 min",
                tip="Never vortex or pipette-mix competent cells vigorously; they are extremely fragile!"
            ),
            ProtocolStep(
                step_number=2,
                title="DNA Addition",
                instruction="Add 1.0–2.0 µL of purified plasmid (10–50 ng) or 2.0–4.0 µL of unpurified Gibson assembly / ligation reaction directly into the 50 µL cell suspension. Flick tube gently 2–3 times to distribute DNA.",
                temperature="0°C (wet ice)",
                duration="2 min",
                tip="Excess salt from ligation reactions can inhibit transformation; keep DNA volume <= 10% of cell volume."
            ),
            ProtocolStep(
                step_number=3,
                title="Ice Incubation",
                instruction="Incubate the DNA-cell mixture on ice for 30 minutes without disturbance.",
                temperature="0°C (wet ice)",
                duration="30 min",
                tip="Shortening ice incubation below 20 min significantly reduces transformation efficiency."
            ),
            ProtocolStep(
                step_number=4,
                title="Heat Shock",
                instruction="Transfer the tubes directly into a pre-calibrated 42°C water bath for exactly 45 seconds (or 60 seconds in a heat block). Do not agitate.",
                temperature="42.0°C",
                duration="45–60 sec",
                tip="Timing is critical! Over-exposure to 42°C kills the cells; under-exposure fails to trigger DNA uptake."
            ),
            ProtocolStep(
                step_number=5,
                title="Cold Snap",
                instruction="Immediately return tubes to wet ice and incubate for 2 minutes.",
                temperature="0°C (wet ice)",
                duration="2 min",
                tip="Rapid chilling reseals cell membranes around the internalized plasmid."
            ),
            ProtocolStep(
                step_number=6,
                title="Outgrowth Recovery",
                instruction="Aseptically add 950 µL of room-temperature SOC medium to each tube. Place horizontally in a 37°C shaking incubator at 225–250 rpm for 60 minutes.",
                temperature="37°C",
                duration="60 min",
                tip="For Ampicillin selection, 30–45 min is sufficient; for Kanamycin, Chloramphenicol, or Tetracycline, a full 60 min is strictly required."
            ),
            ProtocolStep(
                step_number=7,
                title="Plating & Incubation",
                instruction="Mix by gentle inversion. Plate 50 µL and 200 µL of outgrown cells onto pre-warmed selective LB agar plates. Spread evenly using a sterile spreader until dry. Invert plates and incubate overnight at 37°C (14–18 hours).",
                temperature="37°C",
                duration="14–18 hours",
                tip="If transforming a low-efficiency ligation, pellet remaining cells (3 min at 4,000 x g), resuspend in 100 µL, and plate all."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="Zero colonies on selective plate",
                possible_cause="Heat shock temperature exceeded 42°C, antibiotic concentration in agar was too high, or cells lost competency.",
                solution="Verify water bath temp with an independent thermometer. Include a positive control transformation with 10 pg pUC19."
            ),
            TroubleshootingItem(
                issue="Dense lawn of bacteria instead of discrete colonies",
                possible_cause="Antibiotic omitted or degraded, or excessive DNA input.",
                solution="Prepare fresh selective plates. Dilute transformation mixture 1:100 in SOC before plating."
            ),
            TroubleshootingItem(
                issue="Satellite colonies surrounding main colonies",
                possible_cause="Secreted beta-lactamase (bla / AmpR) degrades ampicillin in surrounding agar during extended incubation (>18 h).",
                solution="Pick colonies promptly at 14–16 hours, or switch to carbenicillin (100 µg/mL), which is more stable than ampicillin."
            )
        ],
        references=[
            "Inoue, H., Nojima, H., & Okayama, H. (1990). High efficiency transformation of Escherichia coli with plasmids. Gene, 96(1), 23-28.",
            "Froger, A., & Hall, J. E. (2007). Transformation of plasmid DNA into E. coli using the heat shock method. Journal of Visualized Experiments, (6), 253."
        ]
    ),

    "alkaline_lysis_miniprep": LabProtocol(
        protocol_id="alkaline_lysis_miniprep",
        title="Alkaline Lysis Plasmid DNA Miniprep",
        category="Cloning & DNA Isolation",
        summary="Classic Birnboim & Doly alkaline lysis protocol with silica spin column binding for isolation of high-purity plasmid DNA from 1–5 mL E. coli overnight cultures.",
        estimated_time="25–35 minutes",
        skill_level="Beginner",
        safety_notes=[
            "Buffer P2 contains 0.2 M NaOH and 1% SDS (corrosive, irritant). Wear gloves and eye protection.",
            "Buffer P3 / N3 contains guanidine hydrochloride (chaotropic salt; harmful if swallowed). Do not mix with bleach (releases toxic chlorine gas).",
            "Wash buffer PE contains ethanol (flammable)."
        ],
        reagents=[
            ProtocolReagent("Overnight E. coli Culture", "OD600 ~ 2.0–3.0", "1.5–5.0 mL", "Grown in LB broth with selective antibiotic"),
            ProtocolReagent("Resuspension Buffer P1", "50 mM Tris, 10 mM EDTA, pH 8.0", "250 µL", "Contains 100 µg/mL RNase A; store at 4°C"),
            ProtocolReagent("Lysis Buffer P2", "200 mM NaOH, 1% w/v SDS", "250 µL", "Store at RT; warm if SDS precipitates"),
            ProtocolReagent("Neutralization Buffer P3 / N3", "3.0 M Potassium Acetate, pH 5.5", "350 µL", "Acidic potassium salt precipitates SDS and gDNA"),
            ProtocolReagent("Wash Buffer PB", "Guanidine hydrochloride, isopropanol", "500 µL", "Optional for endA+ strains like BL21 to remove nucleases"),
            ProtocolReagent("Wash Buffer PE", "80% Ethanol, 10 mM Tris-HCl", "700 µL", "Ensure 100% ethanol was added prior to first use"),
            ProtocolReagent("Elution Buffer EB", "10 mM Tris-HCl, pH 8.5", "50 µL", "Or sterile nuclease-free water (pH 7.0–8.5)"),
        ],
        materials_equipment=[
            "Benchtop microcentrifuge capable of 13,000–16,000 x g",
            "Silica membrane micro-spin columns with 2.0 mL collection tubes",
            "Sterile 1.5 mL microcentrifuge tubes",
            "NanoDrop spectrophotometer for A260/A280 quantification",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Cell Harvesting",
                instruction="Pellet 1.5–3.0 mL of overnight culture in a 1.5 mL tube by centrifuging at 8,000 x g for 2 minutes at room temperature. Discard supernatant thoroughly by decanting or aspirating with a pipette.",
                temperature="20–25°C",
                duration="3 min",
                tip="A dry pellet ensures no residual LB media dilutes the alkaline lysis buffers."
            ),
            ProtocolStep(
                step_number=2,
                title="Cell Resuspension",
                instruction="Add 250 µL of chilled Buffer P1 (containing RNase A). Resuspend bacterial pellet completely by vortexing or pipetting up and down until no cell clumps remain.",
                temperature="4°C / RT",
                duration="2 min",
                tip="Incomplete resuspension leaves clumps that fail to lyse, dramatically lowering yield."
            ),
            ProtocolStep(
                step_number=3,
                title="Alkaline Lysis",
                instruction="Add 250 µL of Buffer P2. Invert tube gently 4–6 times to mix. The solution will transition from cloudy to clear and viscous as cells lyse. DO NOT VORTEX. Incubate at room temperature for NO MORE than 4 minutes.",
                temperature="20–25°C",
                duration="3–4 min",
                tip="CRITICAL: Never vortex after adding P2! Vortexing shears chromosomal DNA, which co-purifies with plasmid DNA. Never exceed 5 min to avoid irreversible plasmid denaturation."
            ),
            ProtocolStep(
                step_number=4,
                title="Neutralization",
                instruction="Add 350 µL of Buffer P3 (or N3). Immediately invert gently 6–8 times. A fluffy white precipitate of potassium dodecyl sulfate (KDS), protein, and genomic DNA will form.",
                temperature="20–25°C",
                duration="2 min",
                tip="Mix immediately upon P3 addition to prevent localized denaturation of plasmid DNA."
            ),
            ProtocolStep(
                step_number=5,
                title="Centrifugation of Lysate",
                instruction="Centrifuge the neutralized lysate at maximum speed (13,000–16,000 x g) for 10 minutes at room temperature. A tight white pellet forms at the bottom and side of the tube.",
                temperature="20–25°C",
                duration="10 min",
                tip="If the supernatant is not completely clear, re-spin for an additional 2 minutes."
            ),
            ProtocolStep(
                step_number=6,
                title="Silica Column Binding",
                instruction="Carefully pipette the clear supernatant (~800 µL) into a silica spin column placed in a 2 mL collection tube, avoiding the white precipitate. Centrifuge at 12,000 x g for 60 seconds. Discard flow-through.",
                temperature="20–25°C",
                duration="2 min",
                tip="Do not transfer any white precipitate; debris will clog the silica membrane."
            ),
            ProtocolStep(
                step_number=7,
                title="Column Washing",
                instruction="(Optional: Add 500 µL Buffer PB and spin 60 s for endA+ strains). Add 700 µL of Buffer PE (containing ethanol). Centrifuge at 12,000 x g for 60 seconds. Discard flow-through. Centrifuge empty column for an additional 120 seconds to completely remove residual ethanol.",
                temperature="20–25°C",
                duration="3 min",
                tip="Residual ethanol in eluted plasmid inhibits downstream restriction digests and PCR reactions!"
            ),
            ProtocolStep(
                step_number=8,
                title="Plasmid Elution",
                instruction="Transfer column to a clean, labeled 1.5 mL microcentrifuge tube. Add 50 µL of Buffer EB (10 mM Tris-HCl, pH 8.5) directly to the center of the silica membrane. Incubate at room temperature for 2 minutes. Centrifuge at 12,000 x g for 60 seconds.",
                temperature="20–25°C",
                duration="3 min",
                tip="Pre-warming Buffer EB to 55°C improves recovery for larger plasmids (>10 kb)."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="Low plasmid yield (<2 µg from 3 mL culture)",
                possible_cause="Low copy number plasmid (e.g. pBR322 vs high-copy pUC/pET), incomplete resuspension, or antibiotic degradation.",
                solution="Increase culture volume for low-copy vectors (5–10 mL). Verify antibiotic potency. Ensure complete pellet resuspension in P1."
            ),
            TroubleshootingItem(
                issue="Contaminating genomic DNA on agarose gel (smear or band >20 kb)",
                possible_cause="Vigorous shaking or vortexing after adding Buffer P2 or P3.",
                solution="Mix exclusively by gentle inversion (4–6 times). Never vortex lysed cells."
            ),
            TroubleshootingItem(
                issue="Denatured supercoiled plasmid DNA (migrates faster than supercoiled monomer)",
                possible_cause="Lysis with Buffer P2 exceeded 5 minutes, permanently denaturing strands.",
                solution="Strictly limit P2 incubation to 3–4 minutes before neutralizing with P3."
            )
        ],
        references=[
            "Birnboim, H. C., & Doly, J. (1979). A rapid alkaline extraction procedure for screening recombinant plasmid DNA. Nucleic Acids Research, 7(6), 1513-1523. DOI: 10.1093/nar/7.6.1513",
            "Sambrook, J., & Russell, D. W. (2001). Molecular Cloning: A Laboratory Manual (3rd ed., Vol. 1, pp. 1.32-1.35). Cold Spring Harbor Laboratory Press.",
            "Ish-Horowicz, D., & Burke, J. F. (1981). Rapid and efficient cosmid cloning. Nucleic Acids Research, 9(13), 2989-2998."
        ]
    ),

    "agarose_gel_electrophoresis": LabProtocol(
        protocol_id="agarose_gel_electrophoresis",
        title="Agarose Gel Electrophoresis for DNA & RNA Fragment Sizing",
        category="Electrophoresis",
        summary="Casting, loading, running, and imaging of submarine agarose gels for resolving, quantifying, and analyzing double-stranded DNA fragments (100 bp to 10 kb) and native RNA.",
        estimated_time="1.0–1.5 hours",
        skill_level="Beginner",
        safety_notes=[
            "Molten agarose causes severe scald burns. Use thermal heat-resistant silicone gloves when handling microwaved flasks.",
            "DNA fluorescent stains (GelRed, Ethidium Bromide, SYBR Safe) are mutagens/intercalating agents. Handle with gloves and dispose of in designated gel waste.",
            "Wear UV-blocking face shield or blue-light protective glasses when visualizing bands."
        ],
        reagents=[
            ProtocolReagent("Molecular Biology Grade Agarose Powder", "100%", "1.0 g (for 1% gel)", "Low EEO agarose for general DNA resolution"),
            ProtocolReagent("1X TAE or 1X TBE Electrophoresis Buffer", "1X", "500 mL", "100 mL for gel casting, ~400 mL for tank buffer"),
            ProtocolReagent("Nucleic Acid Intercalating Stain", "10,000X in water", "10 µL per 100 mL gel", "GelRed, SYBR Safe, or Ethidium Bromide (0.5 µg/mL)"),
            ProtocolReagent("6X DNA Loading Dye", "6X", "2.0 µL per 10 µL sample", "Bromophenol blue / xylene cyanol with 30% glycerol"),
            ProtocolReagent("DNA Molecular Weight Ladder (1 kb or 100 bp)", "Ready-to-load", "5.0 µL per lane", "1 kb Plus Ladder for 500 bp–10 kb; 100 bp for 100–1000 bp"),
        ],
        materials_equipment=[
            "Microwave oven with variable power settings",
            "250 mL or 500 mL Erlenmeyer flask (volume >= 2.5x gel volume)",
            "Gel casting tray, rubber gaskets/casting gates, and well combs (8, 10, or 15-tooth)",
            "Submarine horizontal electrophoresis tank and DC power supply (0–300 V)",
            "UV transilluminator or blue-light LED imaging darkroom enclosure with camera",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Prepare Agarose Slurry",
                instruction="Weigh 1.0 g agarose (for a 1% w/v gel, optimal for 500–5,000 bp; use 1.5–2.0% for 100–500 bp) into a 250 mL flask. Add 100 mL of 1X TAE (or 1X TBE) buffer. Swirl gently to suspend powder.",
                temperature="20–25°C",
                duration="2 min",
                tip="Always use the same buffer batch (e.g. 1X TAE) for BOTH casting the gel and filling the running tank!"
            ),
            ProtocolStep(
                step_number=2,
                title="Microwave Dissolution",
                instruction="Microwave on high power for 60 seconds. Stop and swirl gently (watch for boiling bubbles). Microwave in 15-second bursts until solution is completely clear with no visible 'lens' particles or grains.",
                temperature="~100°C",
                duration="3 min",
                tip="Agarose can superheat and boil over violently; wear silicone safety gloves and do not point the flask neck at anyone."
            ),
            ProtocolStep(
                step_number=3,
                title="Cooling & Stain Addition",
                instruction="Allow molten agarose to cool to 50–55°C (comfortable to hold the flask against a gloved hand for 5 seconds). Add 10 µL of 10,000X GelRed or SYBR Safe. Swirl thoroughly to disperse.",
                temperature="50–55°C",
                duration="10 min",
                tip="Adding stain to boiling agarose degrades the fluorescent dye and produces toxic vapors."
            ),
            ProtocolStep(
                step_number=4,
                title="Casting the Gel",
                instruction="Seat the casting tray level on the bench. Place the comb near the cathode (-) end. Slowly pour molten agarose into the tray. Dislodge any air bubbles to the gel edge using a clean pipette tip. Allow to solidify completely for 30 minutes at room temperature.",
                temperature="20–25°C",
                duration="30 min",
                tip="A fully polymerized gel appears translucent and milky white; the surface is firm to gentle touch."
            ),
            ProtocolStep(
                step_number=5,
                title="Tank Setup & Comb Removal",
                instruction="Carefully pull the comb straight up in one smooth motion to avoid tearing wells. Transfer tray to the electrophoresis chamber with wells oriented toward the negative (black / cathode) terminal. Fill tank with 1X running buffer until submerged under 2–3 mm of buffer.",
                temperature="20–25°C",
                duration="5 min",
                tip="DNA is negatively charged and runs towards the positive (red / anode) pole: 'Run to Red'!"
            ),
            ProtocolStep(
                step_number=6,
                title="Sample Loading",
                instruction="Mix DNA samples with 6X Loading Dye (e.g., 2.0 µL 6X dye + 10.0 µL DNA). Load 5.0 µL DNA ladder into Lane 1. Pipette samples into subsequent wells, resting the pipette tip gently just inside the well mouth.",
                temperature="20–25°C",
                duration="5 min",
                tip="Do not puncture the bottom of the well with the pipette tip."
            ),
            ProtocolStep(
                step_number=7,
                title="Electrophoresis Run",
                instruction="Attach safety lid matching colors (black to black, red to red). Run at constant voltage of 5–8 V per cm of inter-electrode distance (typically 90–120 V for standard chambers) for 45–60 minutes. Monitor dye fronts (Bromophenol blue runs at ~300 bp, Xylene cyanol at ~4,000 bp in 1% agarose).",
                temperature="20–25°C",
                duration="45–60 min",
                tip="Running above 130 V generates excessive Joule heat, causing bands to smile and the gel to melt."
            ),
            ProtocolStep(
                step_number=8,
                title="Visualization & Gel Documentation",
                instruction="Turn off power supply. Disconnect leads and carefully transfer gel to UV or blue-light transilluminator. Capture digital image with proper exposure to prevent saturated bands.",
                temperature="20–25°C",
                duration="5 min",
                tip="Blue light illumination (470 nm) prevents UV-induced thymine dimerization, preserving DNA viability for downstream cloning."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="Smiled or distorted, curved bands",
                possible_cause="Voltage set too high (>10 V/cm), buffer depleted, or uneven gel cooling.",
                solution="Reduce voltage to 80–100 V. Prepare fresh 1X running buffer."
            ),
            TroubleshootingItem(
                issue="Samples floated out of wells upon loading",
                possible_cause="Insufficient loading dye / glycerol density agent, or residual ethanol in DNA sample.",
                solution="Ensure 6X loading dye is added to 1X final. Vacuum-dry DNA pellets to remove ethanol before loading."
            ),
            TroubleshootingItem(
                issue="Faint or absent DNA bands",
                possible_cause="Insufficient DNA loaded (<10 ng), dye omitted, or ran in the wrong direction (positive to negative).",
                solution="Load at least 20–50 ng per band. Verify 'Run to Red' orientation. Post-stain the gel in 3X GelRed for 30 minutes if stain was forgotten."
            )
        ],
        references=[
            "Sharp, P. A., Sugden, B., & Sambrook, J. (1973). Detection of two restriction endonuclease activities in Haemophilus parainfluenzae using analytical agarose-ethidium bromide electrophoresis. Biochemistry, 12(16), 3055-3063. DOI: 10.1021/bi00740a018",
            "Lee, P. Y., Costumbrado, J., Hsu, C. Y., & Kim, Y. H. (2012). Agarose gel electrophoresis for the separation of DNA fragments. Journal of Visualized Experiments, (62), e3923. DOI: 10.3791/3923",
            "Green, M. R., & Sambrook, J. (2012). Analysis of DNA by agarose gel electrophoresis. Cold Spring Harbor Protocols, 2019(1), pdb.prot100404."
        ]
    ),

    "ethanol_precipitation": LabProtocol(
        protocol_id="ethanol_precipitation",
        title="Ethanol & Isopropanol Nucleic Acid Precipitation & Desalting",
        category="Solutions & Reagents",
        summary="High-recovery alcohol precipitation for concentrating, desalting, and purifying DNA or RNA solutions from enzymatic reactions or crude lysates.",
        estimated_time="1.0–1.5 hours",
        skill_level="Beginner",
        safety_notes=[
            "100% Ethanol and Isopropanol are volatile and highly flammable. Keep away from open flames and sparks.",
            "Use RNase-free certified reagents, tips, and low-binding microcentrifuge tubes when precipitating RNA."
        ],
        reagents=[
            ProtocolReagent("Nucleic Acid Sample (DNA or RNA)", "Variable", "50–500 µL", "Aqueous solution"),
            ProtocolReagent("3.0 M Sodium Acetate (pH 5.2)", "3.0 M", "0.10 volume", "Standard salt for routine DNA/RNA recovery"),
            ProtocolReagent("Glycogen or GlycoBlue Carrier", "15–20 mg/mL", "1.0 µL (15–20 µg)", "Recommended for low concentrations (<10 ng/µL)"),
            ProtocolReagent("100% Molecular Grade Ethanol (Ice-cold)", "100%", "2.5–3.0 volumes", "Chilled at -20°C prior to use"),
            ProtocolReagent("70% Ethanol (Ice-cold)", "70% v/v in ddH2O", "1.0 mL per tube", "For salt wash"),
            ProtocolReagent("1X TE Buffer (pH 8.0) or nuclease-free water", "1X or pure water", "20–50 µL", "For final resuspension"),
        ],
        materials_equipment=[
            "Refrigerated benchtop microcentrifuge capable of >= 16,000 x g at 4°C",
            "-20°C or -80°C freezer",
            "1.5 mL low-retention microcentrifuge tubes",
            "Fine-drawn pipette tips for supernatant removal",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Salt & Carrier Addition",
                instruction="To the aqueous DNA/RNA solution, add 0.10 volume of 3.0 M Sodium Acetate (pH 5.2) (e.g. 10 µL for a 100 µL sample). Add 1.0 µL of GlycoBlue or glycogen carrier if sample quantity is < 1 µg.",
                temperature="20–25°C",
                duration="1 min",
                tip="GlycoBlue stains the pellet vivid blue, making tiny picomole nucleic acid pellets easily visible."
            ),
            ProtocolStep(
                step_number=2,
                title="Alcohol Addition & Mixing",
                instruction="Add 2.5 to 3.0 volumes of ice-cold 100% ethanol (e.g. 250–300 µL for a 100 µL sample) OR 0.7 to 1.0 volume of 100% isopropanol. Invert tube vigorously 10 times to mix thoroughly.",
                temperature="20–25°C",
                duration="2 min",
                tip="Isopropanol requires less volume, making it ideal for samples >400 µL in standard 1.5 mL tubes."
            ),
            ProtocolStep(
                step_number=3,
                title="Chilled Incubation",
                instruction="Incubate at -20°C for at least 30 minutes (or -80°C for 15–20 minutes). For short RNA oligos (<40 nt), incubate overnight at -20°C.",
                temperature="-20°C to -80°C",
                duration="30–60 min",
                tip="Extended incubation at -80°C does not harm nucleic acids and maximizes recovery of dilute samples."
            ),
            ProtocolStep(
                step_number=4,
                title="High-Speed Centrifugation",
                instruction="Centrifuge at maximum speed (>= 16,000 x g) for 25–30 minutes at 4°C. Place tube hinges facing outward so the pellet forms reliably on the hinge side.",
                temperature="4.0°C",
                duration="30 min",
                tip="Aligning tube hinges outward allows you to know exactly where invisible pellets reside."
            ),
            ProtocolStep(
                step_number=5,
                title="Supernatant Removal",
                instruction="Carefully remove tubes from centrifuge without disturbing the pellet. Slowly pipette off the supernatant and discard. A small blue or white pellet should be visible at the bottom hinge side.",
                temperature="20–25°C",
                duration="3 min",
                tip="Do not pour off supernatant; use a P1000 tip down to the last 50 µL, then a P20 tip for the remainder."
            ),
            ProtocolStep(
                step_number=6,
                title="70% Ethanol Salt Wash",
                instruction="Add 500–1000 µL of ice-cold 70% ethanol without dislodging the pellet. Centrifuge at >= 16,000 x g for 5 minutes at 4°C. Aspirate all supernatant with a fine P10 tip.",
                temperature="4.0°C",
                duration="5 min",
                tip="The 70% ethanol wash dissolves co-precipitated sodium acetate salts while leaving nucleic acids insoluble."
            ),
            ProtocolStep(
                step_number=7,
                title="Air Drying & Resuspension",
                instruction="Air-dry the open tube on the bench for 3–5 minutes until the pellet turns from translucent/milky to clear. DO NOT over-dry. Add 20–50 µL of 1X TE buffer (pH 8.0) or nuclease-free water. Incubate at room temperature for 10 minutes to resuspend.",
                temperature="20–25°C",
                duration="15 min",
                tip="Over-dried DNA pellets become vitreous and refractory to re-dissolution; gentle warming at 55°C aids dissolution."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="No pellet visible after centrifugation",
                possible_cause="Nucleic acid concentration was very low (<5 ng/µL) and no carrier was used, or pellet was aspirated.",
                solution="Always add 1 µL GlycoBlue carrier for low-input samples. Re-centrifuge for 30 minutes at 4°C."
            ),
            TroubleshootingItem(
                issue="Pellet will not dissolve in water/TE",
                possible_cause="Pellet was over-dried in a vacuum concentrator (SpeedVac) or air-dried for >20 minutes.",
                solution="Incubate at 50–55°C with intermittent vortexing for 15–30 minutes."
            ),
            TroubleshootingItem(
                issue="High salt carryover (low A260/A230 ratio < 1.5)",
                possible_cause="Supernatant not fully removed before or after the 70% ethanol wash.",
                solution="Perform a second 70% ethanol wash and spin; remove every droplet with a P10 pipette tip."
            )
        ],
        references=[
            "Zeugin, J. A., & Hartley, J. L. (1985). Ethanol precipitation of DNA. Focus, 7(4), 1-2.",
            "Green, M. R., & Sambrook, J. (2012). Molecular Cloning: A Laboratory Manual. Cold Spring Harbor Laboratory Press."
        ]
    ),

    "gibson_assembly": LabProtocol(
        protocol_id="gibson_assembly",
        title="Gibson Isothermal DNA Assembly (2–3 Fragments)",
        category="Molecular Cloning",
        summary="One-pot isothermal in vitro assembly of multiple overlapping DNA fragments using 5' T5 exonuclease, Phusion DNA polymerase, and Taq DNA ligase.",
        estimated_time="1.0 hour (reaction) + transformation",
        skill_level="Intermediate",
        safety_notes=[
            "Gibson 2X Master Mix contains active enzymes and sensitive cofactors (NAD+, ATP). Keep on ice while setting up reactions.",
            "Protect Gibson Master Mix from repeated freeze-thaw cycles by preparing single-use 10 µL aliquots."
        ],
        reagents=[
            ProtocolReagent("2X Gibson Assembly Master Mix", "2X", "10.0 µL (for 20 µL rxn)", "T5 exonuclease, Phusion polymerase, Taq ligase"),
            ProtocolReagent("Linearized Vector DNA", "20–100 ng/µL", "50–100 ng (0.02–0.05 pmol)", "Contains 20–40 bp overlaps with inserts"),
            ProtocolReagent("DNA Insert Fragment(s)", "20–100 ng/µL", "2:1 or 3:1 molar ratio to vector", "Contains 20–40 bp overlaps"),
            ProtocolReagent("Deionized Nuclease-Free Water", "Molecular grade", "QS to 20.0 µL", "-"),
            ProtocolReagent("Chemically Competent E. coli (DH5alpha / NEB 5-alpha)", ">= 1e8 cfu/µg", "50 µL per transformation", "For subsequent transformation"),
        ],
        materials_equipment=[
            "Calibrated thermal cycler set to constant 50°C",
            "0.2 mL thin-walled PCR tubes",
            "Fluorometer (Qubit) or NanoDrop for precision DNA quantification",
            "Heat shock transformation apparatus and selective agar plates",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Overlap & Molar Ratio Calculation",
                instruction="Verify that all fragments have 20–40 bp homologous overlapping ends with Tm >= 48°C. For a 2-fragment assembly, use a 2:1 to 3:1 molar ratio of insert to vector. Use total DNA of 0.02–0.5 pmol (typically 50–100 ng vector + calculated insert mass).",
                temperature="20–25°C",
                duration="5 min",
                tip="Use BioLabCalc's 'biolabcalc gibson' CLI to calculate exact molar masses and pipetting volumes."
            ),
            ProtocolStep(
                step_number=2,
                title="Reaction Setup",
                instruction="Set up the assembly reaction on ice in a 0.2 mL PCR tube: Add vector DNA, insert DNA, and nuclease-free water to a volume of 10.0 µL. Add 10.0 µL of 2X Gibson Assembly Master Mix. Pipette mix gently.",
                temperature="0°C (ice)",
                duration="3 min",
                tip="Keep total DNA volume <= 10 µL so master mix is exactly 1X."
            ),
            ProtocolStep(
                step_number=3,
                title="Isothermal Incubation",
                instruction="Place reaction in a pre-heated thermal cycler set to 50°C with heated lid (set to 60°C or off). Incubate at 50°C for 15 minutes (for 2–3 fragments) or 60 minutes (for 4–6 fragments).",
                temperature="50.0°C",
                duration="15–60 min",
                tip="Do not exceed 60 min; T5 exonuclease activity can chew back beyond the overlap regions."
            ),
            ProtocolStep(
                step_number=4,
                title="Cooling & Storage",
                instruction="Following 50°C incubation, immediately place the reaction on ice or store at -20°C until transformation.",
                temperature="4°C / ice",
                duration="2 min",
                tip="Assembled product is stable at -20°C for several weeks."
            ),
            ProtocolStep(
                step_number=5,
                title="Transformation into Competent Cells",
                instruction="Transform 2.0 µL of the assembled reaction mixture into 50 µL of chemically competent E. coli cells using the standard heat-shock protocol. Plate 100 µL on selective agar plates.",
                temperature="42°C heat shock",
                duration="1.5 hours",
                tip="Do not add more than 2–3 µL of Gibson mix to 50 µL cells; PEG in master mix inhibits transformation."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="Low colony count or empty vector background",
                possible_cause="Homology arms <20 bp, secondary structure in overlaps, or incomplete vector linearization.",
                solution="Ensure 25–30 bp overlaps. Treat linearized vector with DpnI if PCR-derived, or rSAP if restriction-digested."
            ),
            TroubleshootingItem(
                issue="Transformant colonies contain incorrect deletions",
                possible_cause="Reaction incubated at 50°C for too long, chewing into coding sequence.",
                solution="Strictly limit 2-fragment assembly to 15 minutes at 50°C."
            )
        ],
        references=[
            "Gibson, D. G., Young, L., Chuang, R. Y., Venter, J. C., Hutchison, C. A., & Smith, H. O. (2009). Enzymatic assembly of DNA molecules up to several hundred kilobases. Nature Methods, 6(5), 343-345. DOI: 10.1038/nmeth.1318",
            "Gibson, D. G., et al. (2010). Creation of a bacterial cell controlled by a chemically synthesized genome. Science, 329(5987), 52-56. DOI: 10.1126/science.1190719"
        ]
    ),

    "denaturing_urea_page": LabProtocol(
        protocol_id="denaturing_urea_page",
        title="Denaturing Urea-PAGE (7–8 M Urea) for Short RNAs & Aptamers",
        category="Electrophoresis",
        summary="High-resolution polyacrylamide gel electrophoresis under denaturing conditions (7–8 M urea, 50–55°C) for single-nucleotide resolution of synthetic RNA oligos, aptamers, and in vitro transcripts (15–300 nt).",
        estimated_time="3.0–4.0 hours",
        skill_level="Advanced",
        safety_notes=[
            "Unpolymerized acrylamide is a potent cumulative neurotoxin and suspected carcinogen. Wear nitrile gloves and dispense liquid stock in a dedicated fume hood.",
            "TEMED has an offensive odor and causes respiratory irritation. Pipette in a fume hood.",
            "Ammonium persulfate (APS) is a strong oxidizer and skin sensitizer."
        ],
        reagents=[
            ProtocolReagent("29:1 Acrylamide:Bis-acrylamide (40% stock)", "40% w/v", "10–25 mL", "Neurotoxin; store at 4°C in dark"),
            ProtocolReagent("UltraPure Urea", "Solid crystals", "21.0 g (for 50 mL 7 M gel)", "Denaturing agent"),
            ProtocolReagent("10X TBE Electrophoresis Buffer", "10X", "5.0 mL (gel) + 100 mL (running)", "890 mM Tris, 890 mM Boric acid, 20 mM EDTA"),
            ProtocolReagent("10% Ammonium Persulfate (APS)", "10% w/v in water", "350 µL", "Freshly prepared (<1 week old)"),
            ProtocolReagent("TEMED", "Pure liquid", "35 µL", "Polymerization catalyst"),
            ProtocolReagent("2X Denaturing RNA Loading Dye", "2X", "Equal volume to sample", "95% Formamide, 10 mM EDTA, 0.025% SDS, xylene cyanol, bromophenol blue"),
            ProtocolReagent("Methylene Blue (0.02%) or GelRed Stain", "0.02% w/v or 3X", "100 mL", "For post-electrophoretic RNA visualization"),
        ],
        materials_equipment=[
            "Vertical slab gel apparatus (16x18 cm or 20x20 cm glass plates, 0.75 or 1.5 mm spacers, sharkstooth or square-well comb)",
            "High-voltage DC power supply capable of 500–2,000 V (constant wattage)",
            "Heating block or PCR cycler set to 90°C for sample denaturation",
            "Aluminum heat-dispersal backing plate",
            "Flat gel loading tips (0.4 mm)",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Assemble Glass Cassette",
                instruction="Clean glass plates meticulously with deionized water, followed by 70% ethanol. Treat notched plate with Gel Slick / Sigmacote (optional) for easy release. Assemble with 0.75 mm spacers and clamp securely.",
                temperature="20–25°C",
                duration="10 min",
                tip="Dust particles or grease fingerprints cause bubbles and distorted, wavy lanes."
            ),
            ProtocolStep(
                step_number=2,
                title="Prepare Acrylamide / Urea Solution",
                instruction="For a 10% gel (50 mL): dissolve 21.0 g urea (7 M final) in 12.5 mL 40% acrylamide (29:1), 5.0 mL 10X TBE, and ~15 mL ddH2O. Warm gently in warm water bath to dissolve urea. Bring volume to 50 mL with water and filter through 0.45 µm filter.",
                temperature="30–37°C",
                duration="15 min",
                tip="Do not overheat; urea hydrolyzes to cyanate at >50°C, which carbamylates nucleic acids."
            ),
            ProtocolStep(
                step_number=3,
                title="Initiate Polymerization & Pour Gel",
                instruction="Add 350 µL 10% APS and 35 µL TEMED. Swirl gently for 5 seconds. Immediately pour into casting cassette using a 50 mL syringe. Insert comb and allow to polymerize for 45–60 minutes.",
                temperature="20–25°C",
                duration="45–60 min",
                tip="Polymerization is inhibited by oxygen; clamp top edges firmly."
            ),
            ProtocolStep(
                step_number=4,
                title="Pre-run & Warm Cassette",
                instruction="Mount gel in vertical tank with 1X TBE. Flush urea leached into wells vigorously with a syringe. Pre-run gel at constant 30–45 Watts (approx 1,200–1,500 V) for 30 minutes until surface temp reaches 50–55°C.",
                temperature="50–55°C",
                duration="30 min",
                tip="Pre-heating is essential to maintain complete denaturing conditions during electrophoresis."
            ),
            ProtocolStep(
                step_number=5,
                title="Sample Denaturation & Loading",
                instruction="Mix RNA samples 1:1 with 2X Formamide Loading Buffer. Heat at 90–95°C for 3 minutes, then snap-chill immediately on wet ice. Flush wells once more with 1X TBE, and load samples using micro-loading tips.",
                temperature="90°C -> 0°C",
                duration="5 min",
                tip="Snap-cooling prevents secondary hairpins and G-quadruplexes from re-annealing."
            ),
            ProtocolStep(
                step_number=6,
                title="Electrophoresis Run",
                instruction="Run at constant 30–40 W (50°C gel temperature) until the bromophenol blue (runs like ~8–12 nt RNA in 10% gel) and xylene cyanol (~55 nt in 10% gel) migrate to desired positions.",
                temperature="50–55°C",
                duration="1.5–2.5 hours",
                tip="Maintain 50°C; if gel cools down, RNA partially refolds into multiple conformational bands."
            ),
            ProtocolStep(
                step_number=7,
                title="Staining & Band Excision",
                instruction="Pry plates open. Stain in 0.02% Methylene Blue in water for 15 minutes, then destain in ddH2O (or stain in 3X GelRed for 20 min). Visualize bands under white light or UV/blue light.",
                temperature="20–25°C",
                duration="30 min",
                tip="Methylene blue enables clear visible inspection on a light box without UV-induced damage."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="Doublet or diffuse fuzzy bands for single homogeneous RNA",
                possible_cause="Gel temperature dropped below 45°C during run, allowing partial folding/duplex formation.",
                solution="Ensure aluminum backing plate is installed; maintain constant 35–45 Watts to keep gel at 50–55°C."
            ),
            TroubleshootingItem(
                issue="Smiles or uneven upward curving at gel edges",
                possible_cause="Uneven heat dissipation; center of gel runs warmer and faster than outer edges.",
                solution="Clamp an aluminum heat-transfer plate to the outside glass surface to equalize thermal distribution."
            )
        ],
        references=[
            "Summer, H., Grämer, R., & Dröge, P. (2009). Denaturing urea-PAGE: a simple method for high-resolution analysis of small RNA molecules. RNA, 15(12), 2369-2374. DOI: 10.1261/rna.1718609",
            "Rio, D. C., Ares, M., Hannon, G. J., & Nilsen, T. W. (2010). Polyacrylamide gel electrophoresis of RNA. Cold Spring Harbor Protocols, 2010(6), pdb.prot5444. DOI: 10.1101/pdb.prot5444"
        ]
    ),

    "restriction_double_digest": LabProtocol(
        protocol_id="restriction_double_digest",
        title="Restriction Endonuclease Double Digestion & Vector Dephosphorylation",
        category="Molecular Cloning",
        summary="Double endonuclease digestion of plasmid vector or PCR inserts with 100% buffer compatibility and alkaline phosphatase dephosphorylation to eliminate empty vector self-ligation.",
        estimated_time="1.5–2.5 hours",
        skill_level="Intermediate",
        safety_notes=[
            "Restriction enzymes are temperature sensitive and stored in 50% glycerol at -20°C. Keep in benchtop cold block; return to freezer immediately.",
            "Do not exceed 10% glycerol in final reaction volume to avoid star activity (non-specific cleavage)."
        ],
        reagents=[
            ProtocolReagent("Plasmid DNA or PCR Product", "100–500 ng/µL", "1.0–2.0 µg (vector) or 500 ng (insert)", "High-purity miniprep DNA"),
            ProtocolReagent("10X rCutSmart / Compatible Buffer", "10X", "5.0 µL (for 50 µL rxn)", "Enzyme manufacturer reaction buffer"),
            ProtocolReagent("Restriction Enzyme 1 (e.g. EcoRI-HF)", "20,000 U/mL", "1.0 µL (10–20 Units)", "High-fidelity version preferred"),
            ProtocolReagent("Restriction Enzyme 2 (e.g. BamHI-HF)", "20,000 U/mL", "1.0 µL (10–20 Units)", "High-fidelity version preferred"),
            ProtocolReagent("Recombinant Shrimp Alkaline Phosphatase (rSAP)", "1,000 U/mL", "1.0 µL (1 Unit)", "For vector dephosphorylation only"),
            ProtocolReagent("Nuclease-Free Water", "Molecular grade", "QS to 50.0 µL", "-"),
        ],
        materials_equipment=[
            "37°C water bath or calibrated heat block",
            "65°C or 80°C heat block for enzyme heat inactivation",
            "Benchtop microcentrifuge and 0.5 mL / 1.5 mL tubes",
            "Agarose gel electrophoresis apparatus for band verification and gel extraction",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Buffer Compatibility & Star Activity Check",
                instruction="Use BioLabCalc's 'biolabcalc digest' command to confirm 100% dual-cleavage activity in the chosen buffer (e.g., rCutSmart for EcoRI-HF and BamHI-HF). Verify neither enzyme exhibits star activity under these conditions.",
                temperature="20–25°C",
                duration="2 min",
                tip="High-fidelity (-HF) enzymes engineered by NEB operate at 100% in rCutSmart with zero star activity."
            ),
            ProtocolStep(
                step_number=2,
                title="Assemble Reaction on Ice",
                instruction="In a sterile 1.5 mL tube, combine on ice: Nuclease-free water (to 50 µL), 5.0 µL 10X rCutSmart buffer, 1.0–2.0 µg DNA, 1.0 µL Enzyme 1 (10–20 U), and 1.0 µL Enzyme 2 (10–20 U). Mix by flicking 4 times and spin down.",
                temperature="0°C (ice)",
                duration="3 min",
                tip="Total enzyme volume (2 µL) is 4% of total reaction volume (50 µL), safely below the 10% glycerol threshold."
            ),
            ProtocolStep(
                step_number=3,
                title="Digest Incubation",
                instruction="Incubate reaction at 37°C for 60 minutes in a water bath or thermal cycler.",
                temperature="37.0°C",
                duration="60 min",
                tip="For rapid screening, Time-Saver qualified enzymes achieve complete digestion in 15 minutes."
            ),
            ProtocolStep(
                step_number=4,
                title="Vector Dephosphorylation (Vector only)",
                instruction="To digested plasmid vector only: add 1.0 µL of rSAP (1 U) directly into the reaction without buffer exchange. Incubate at 37°C for an additional 30 minutes.",
                temperature="37.0°C",
                duration="30 min",
                tip="rSAP removes 5'-phosphates, preventing self-ligation without an insert, slashing colony background by >95%."
            ),
            ProtocolStep(
                step_number=5,
                title="Heat Inactivation & Cleanup",
                instruction="Heat-inactivate enzymes at 80°C for 20 minutes (or 65°C depending on enzyme specs). Resolve on 1% agarose gel and excise target linearized vector/insert bands with a clean scalpel.",
                temperature="80.0°C",
                duration="20 min",
                tip="If enzymes are not heat-inactivatable (e.g. NotI), purify immediately using a silica spin column."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="Incomplete digestion (partial cut bands observed)",
                possible_cause="Too much DNA loaded, salt/ethanol inhibition, or enzyme left out of freezer too long.",
                solution="Ensure DNA is free of salt; limit DNA to 1–2 µg per 50 µL; extend incubation to 2 hours."
            ),
            TroubleshootingItem(
                issue="Non-specific degradation or smearing (star activity)",
                possible_cause="Glycerol concentration exceeded 10% v/v, or non-optimal buffer used.",
                solution="Keep total enzyme volume <= 5 µL in 50 µL; use high-fidelity (-HF) engineered enzymes."
            )
        ],
        references=[
            "Pingoud, A., & Jeltsch, A. (2001). Structure and function of type II restriction endonucleases. Nucleic Acids Research, 29(18), 3705-3727. DOI: 10.1093/nar/29.18.3705",
            "Roberts, R. J., Vincze, T., Posfai, J., & Macelis, D. (2015). REBASE—a database for DNA restriction and modification: enzymes, genes and genomes. Nucleic Acids Research, 43(D1), D298-D299. DOI: 10.1093/nar/gku1046"
        ]
    ),

    "bradford_protein_assay": LabProtocol(
        protocol_id="bradford_protein_assay",
        title="Bradford / BCA Colorimetric Protein Assay with BSA Standard Curve",
        category="Protein Analysis",
        summary="Quantitative measurement of total protein concentration (1–20 µg/mL micro-assay or 100–1,500 µg/mL standard) using Coomassie Brilliant Blue G-250 dye shift from 465 nm to 595 nm.",
        estimated_time="30–45 minutes",
        skill_level="Beginner",
        safety_notes=[
            "Bradford reagent contains phosphoric acid and methanol (corrosive and toxic). Use eye protection and avoid skin contact."
        ],
        reagents=[
            ProtocolReagent("1X Bradford Reagent (Coomassie G-250)", "1X ready-to-use", "1.0 mL per cuvette / 200 µL per microplate well", "Store at 4°C; bring to RT before use"),
            ProtocolReagent("Bovine Serum Albumin (BSA) Standard", "2.0 mg/mL", "500 µL", "Ampule standard in 0.9% saline"),
            ProtocolReagent("Sample Dilution Buffer / 1X PBS", "1X", "5.0 mL", "Must match sample lysis/elution buffer"),
            ProtocolReagent("Unknown Protein Sample(s)", "Unknown", "10–50 µL", "Eluted protein or cell lysate"),
        ],
        materials_equipment=[
            "UV/Vis Spectrophotometer or microplate reader capable of 595 nm absorbance",
            "1.5 mL disposable polystyrene cuvettes or 96-well flat-bottom clear microplate",
            "Vortex mixer and precision pipettes",
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Prepare BSA Standard Dilution Series",
                instruction="Prepare 7 standard concentrations in 1.5 mL tubes using 1X PBS: 0 µg/mL (Blank), 125, 250, 500, 750, 1,000, and 1,500 µg/mL BSA from the 2.0 mg/mL stock.",
                temperature="20–25°C",
                duration="10 min",
                tip="Use the exact same buffer present in the unknown protein sample as the diluent for the BSA standards!"
            ),
            ProtocolStep(
                step_number=2,
                title="Prepare Dilutions of Unknown Samples",
                instruction="Prepare undiluted, 1:5, and 1:20 dilutions of unknown protein samples in buffer to ensure at least one dilution falls within the linear range (100–1,000 µg/mL).",
                temperature="20–25°C",
                duration="5 min",
                tip="Detergents (SDS >0.1%, Triton X-100 >0.1%) interfere with Bradford. If high detergents are present, switch to BCA assay."
            ),
            ProtocolStep(
                step_number=3,
                title="Add Bradford Reagent",
                instruction="Pipette 20 µL of each standard and unknown sample into duplicate wells of a 96-well plate. Add 200 µL of room-temperature Bradford Reagent to each well. Mix gently on a plate shaker for 30 seconds.",
                temperature="20–25°C",
                duration="3 min",
                tip="Avoid producing air bubbles in wells, which artificially scatter light and skew absorbance."
            ),
            ProtocolStep(
                step_number=4,
                title="Incubation",
                instruction="Incubate at room temperature for 10 minutes in the dark.",
                temperature="20–25°C",
                duration="10 min",
                tip="Absorbance at 595 nm increases over time; read between 10 and 30 minutes for consistent results."
            ),
            ProtocolStep(
                step_number=5,
                title="Measure Absorbance at 595 nm",
                instruction="Measure optical density at 595 nm (OD595) on microplate reader. Subtract the 0 µg/mL blank absorbance from all readings. Plot standard curve (OD595 vs BSA concentration) and fit linear regression (R2 should be >= 0.99). Calculate unknown protein concentration using BioLabCalc's standard curve module.",
                temperature="20–25°C",
                duration="5 min",
                tip="Use BioLabCalc's 'biolabcalc.protein.fit_standard_curve' function to automatically compute concentration and R2."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="Precipitate forms immediately upon reagent addition",
                possible_cause="High detergent concentration (>0.1% SDS) or basic pH buffer (>8.5).",
                solution="Dilute sample 1:10 with water, or switch to the BCA (Bicinchoninic Acid) Protein Assay."
            ),
            TroubleshootingItem(
                issue="Non-linear standard curve (R2 < 0.98)",
                possible_cause="Standards improperly diluted or reading exceeded linear absorbance dynamic range (>1.5 AU).",
                solution="Remake standard dilutions carefully; discard standards above 1,500 µg/mL."
            )
        ],
        references=[
            "Bradford, M. M. (1976). A rapid and sensitive method for the quantitation of microgram quantities of protein utilizing the principle of protein-dye binding. Analytical Biochemistry, 72(1-2), 248-254. DOI: 10.1016/0003-2697(76)90527-3",
            "Smith, P. K., et al. (1985). Measurement of protein using bicinchoninic acid. Analytical Biochemistry, 150(1), 76-85. DOI: 10.1016/0003-2697(85)90442-7",
            "Noble, J. E., & Bailey, M. J. (2009). Quantitation of protein. Methods in Enzymology, 463, 73-95. DOI: 10.1016/S0076-6879(09)63008-1"
        ]
    ),
    "western_blotting": LabProtocol(
        protocol_id="western_blotting",
        title="Standard Western Blotting: SDS-PAGE, Wet Tank Electrotransfer & Chemiluminescent Detection",
        category="Protein Analysis",
        summary="Comprehensive end-to-end Western blot protocol for protein biomarker identification, molecular weight verification, and semi-quantitative densitometry. Covers sample lysis with protease/phosphatase inhibitors, SDS-PAGE resolution, Towbin wet tank transfer to PVDF, blocking agent optimization (5% BSA vs 5% milk), and HRP/ECL chemiluminescent detection.",
        estimated_time="1.5 days (Day 1: lysis, gel run, transfer, overnight primary; Day 2: washes, secondary, ECL imaging)",
        skill_level="Intermediate to Advanced",
        safety_notes=[
            "Unpolymerized acrylamide is a potent neurotoxin and suspected carcinogen; handle cast solutions with nitrile gloves inside fume hood or use pre-cast polyacrylamide gels.",
            "Methanol in Towbin transfer buffer is toxic and volatile; prepare in a well-ventilated area and avoid open flames.",
            "Never add sodium azide (NaN3) to HRP-conjugated antibody solutions; azide irreversibly poisons horseradish peroxidase heme activity."
        ],
        reagents=[
            ProtocolReagent("RIPA Lysis Buffer", "1X", "10 mL", "50 mM Tris-HCl pH 7.4, 150 mM NaCl, 1% NP-40, 0.5% Na-deoxycholate, 0.1% SDS"),
            ProtocolReagent("Protease & Phosphatase Inhibitor Cocktail", "100X stock", "100 µL", "Add fresh to cold RIPA immediately before cell lysis"),
            ProtocolReagent("4X Laemmli Sample Buffer", "4X", "1.0 mL", "250 mM Tris-HCl pH 6.8, 8% SDS, 40% glycerol, 0.04% bromophenol blue"),
            ProtocolReagent("DTT (Dithiothreitol)", "1 M stock", "100 µL", "Add to sample buffer for 100 mM final reducing concentration"),
            ProtocolReagent("1X Tris-Glycine-SDS Running Buffer", "1X", "1000 mL", "25 mM Tris base, 192 mM Glycine, 0.1% SDS, pH ~8.3"),
            ProtocolReagent("1X Towbin Transfer Buffer", "1X", "1000 mL", "25 mM Tris, 192 mM Glycine, 20% Methanol (10% MeOH + 0.05% SDS for >100 kDa)"),
            ProtocolReagent("100% Methanol", "Reagent grade", "50 mL", "For activating hydrophobic PVDF membranes"),
            ProtocolReagent("1X TBST Wash Buffer", "1X", "2000 mL", "20 mM Tris-HCl pH 7.6, 150 mM NaCl, 0.1% Tween-20"),
            ProtocolReagent("Blocking Solution (Phospho-targets)", "5% w/v", "50 mL", "5% BSA in 1X TBST (MILK IS FORBIDDEN FOR PHOSPHO-ANTIBODIES)"),
            ProtocolReagent("Blocking Solution (Standard targets)", "5% w/v", "50 mL", "5% Non-Fat Dry Milk in 1X TBST"),
            ProtocolReagent("Primary Antibody", "User-specified", "5–10 µL", "Typically diluted 1:1,000 in 5% BSA/TBST"),
            ProtocolReagent("HRP-Conjugated Secondary Antibody", "User-specified", "1–2 µL", "Typically diluted 1:5,000 to 1:10,000 in 5% milk/TBST"),
            ProtocolReagent("ECL Chemiluminescent Substrate", "1X working", "2.0 mL", "Clarity Western ECL or SuperSignal West Pico Plus (1:1 mix of Reagents A & B)"),
        ],
        materials_equipment=[
            "Vertical electrophoresis tank and power supply (e.g. Bio-Rad Mini-PROTEAN)",
            "Wet tank transfer unit with internal cooling coil or frozen ice block and stir bar (Mini Trans-Blot)",
            "PVDF membrane (0.45 µm pore size for >25 kDa; 0.2 µm for <25 kDa)",
            "Extra-thick blot filter paper (Whatman 3MM) and foam pads",
            "Pre-stained protein molecular weight ladder (10–250 kDa)",
            "Blot roller or glass pipette to eliminate sandwich air bubbles",
            "Orbital shaker / rocker platform",
            "Cooled CCD chemiluminescent camera (e.g. Bio-Rad ChemiDoc or Azure c600)"
        ],
        steps=[
            ProtocolStep(
                step_number=1,
                title="Cell Lysis & Protein Extraction",
                instruction="Wash cultured cell monolayer twice with ice-cold PBS. Add ice-cold RIPA buffer supplemented with 1X protease/phosphatase inhibitors (100 µL per 10^6 cells). Scrape cells, transfer to pre-chilled microcentrifuge tube, and incubate on ice for 30 minutes with vortexing every 10 min. Centrifuge at 14,000 × g for 15 minutes at 4°C. Transfer supernatant to fresh tube on ice and quantify protein by BCA assay.",
                temperature="4°C",
                duration="45 minutes",
                tip="Keep samples strictly on ice; protease degradation occurs rapidly at room temperature."
            ),
            ProtocolStep(
                step_number=2,
                title="Sample Preparation & Denaturation",
                instruction="Aliquot 20 µg total protein per sample. Add 4X Laemmli sample buffer with 100 mM DTT and balance volumes with lysis buffer. For standard soluble proteins, denature at 95°C for 5 minutes. For multi-pass transmembrane proteins (e.g. GluK2, AMPA receptors, GPCRs), denature at 65°C–70°C for 10 minutes (NEVER boil membrane proteins at 95°C). Centrifuge briefly at 10,000 × g for 30 s before loading.",
                temperature="95°C (soluble) or 70°C (membrane)",
                duration="10 minutes",
                tip="Boiling hydrophobic transmembrane receptors causes irreversible hydrophobic aggregation, trapping them in the well."
            ),
            ProtocolStep(
                step_number=3,
                title="SDS-PAGE Gel Electrophoresis",
                instruction="Assemble gel cassette in running tank and fill inner and outer chambers with 1X Tris-Glycine-SDS running buffer. Load 5 µL pre-stained protein ladder in lane 1. Load 15–20 µL denatured protein samples into adjacent wells. Run at 80 V constant through the stacking gel (~15 min), then increase to 120–130 V constant through the resolving gel (~60–75 min) until the bromophenol blue dye front reaches the bottom of the glass plates.",
                temperature="Room temperature",
                duration="75–90 minutes",
                tip="Running at excessive voltage (>150 V) generates heat, causing smiling bands and partial protein degradation."
            ),
            ProtocolStep(
                step_number=4,
                title="Membrane Activation & Transfer Sandwich Assembly",
                instruction="Pre-wet PVDF membrane in 100% methanol for 1–2 minutes, rinse in water for 2 min, and equilibrate in 1X Towbin transfer buffer for 5 min. Equilibrate SDS-PAGE gel, filter paper, and foam sponges in transfer buffer for 10 min. Assemble sandwich submerged in transfer buffer inside cassette: [Cathode (-) Black side -> Sponge -> Filter Paper -> Gel -> PVDF Membrane -> Filter Paper -> Sponge -> Anode (+) Clear/Red side]. Roll gently with blot roller to expel every air bubble.",
                temperature="Room temperature",
                duration="15 minutes",
                tip="Air bubbles trapped between gel and membrane create blank white voids where proteins cannot transfer."
            ),
            ProtocolStep(
                step_number=5,
                title="Wet Tank Electrotransfer",
                instruction="Insert cassette into transfer tank with black side facing cathode (-) and clear side facing anode (+). Add magnetic stir bar and frozen blue ice block. Fill tank with ice-cold Towbin transfer buffer. Place tank on magnetic stirrer in 4°C cold room. Run at 100 V constant for 60–90 minutes (or 30 V constant overnight for 14–16 hours for proteins >120 kDa).",
                temperature="4°C",
                duration="60–90 minutes (or overnight)",
                tip="For proteins >100 kDa, reduce methanol to 10% and add 0.05% SDS to the transfer buffer to facilitate elution from the gel."
            ),
            ProtocolStep(
                step_number=6,
                title="Transfer Verification & Membrane Blocking",
                instruction="Disassemble sandwich. Rinse membrane in deionized water and stain with 0.1% Ponceau S for 2 minutes on shaker to confirm uniform transfer and equal protein loading across lanes. Image or document lane profiles for Total Protein Normalization (TPN). Wash out Ponceau S with 1X TBST until background is clear. Incubate membrane in 5% BSA in TBST (for phospho-targets) or 5% non-fat milk in TBST (for non-phospho targets) for 1 hour at room temperature with gentle rocking.",
                temperature="Room temperature",
                duration="1 hour 15 minutes",
                tip="Milk contains abundant phospho-casein; blocking with milk for phospho-epitopes produces intense non-specific background."
            ),
            ProtocolStep(
                step_number=7,
                title="Primary Antibody Incubation",
                instruction="Dilute primary antibody (typically 1:1,000) in 5% BSA in TBST (or 5% milk for non-phospho targets). Incubate membrane overnight (14–16 hours) at 4°C with gentle rocking. Alternatively, incubate for 2 hours at room temperature if high-affinity validated antibody is used.",
                temperature="4°C",
                duration="14–16 hours (overnight)",
                tip="Overnight incubation at 4°C consistently yields higher signal-to-noise ratios and lower non-specific background than room temperature incubation."
            ),
            ProtocolStep(
                step_number=8,
                title="Membrane Washing & Secondary Antibody Incubation",
                instruction="Aspirate primary antibody (can be stored with 0.02% sodium azide at 4°C for reuse 2–3 times). Wash membrane 4 times for 5 minutes each with 15 mL 1X TBST under vigorous orbital shaking (~100 rpm). Dilute HRP-conjugated secondary antibody (1:5,000 to 1:10,000) in 5% milk in TBST (DO NOT ADD SODIUM AZIDE). Incubate for 1 hour at room temperature with gentle rocking. Wash membrane 4 times for 5 minutes each with 1X TBST.",
                temperature="Room temperature",
                duration="1 hour 30 minutes",
                tip="Sodium azide irreversibly inhibits HRP. Never add azide to secondary antibody solutions or ECL washes."
            ),
            ProtocolStep(
                step_number=9,
                title="Chemiluminescent Detection & Imaging",
                instruction="Drain excess TBST from membrane and place on clear plastic wrap. Mix equal volumes (1.0 mL each) of ECL Substrate Reagent A (luminol/enhancer) and Reagent B (peroxide). Pipette working solution over membrane, ensuring complete coverage. Incubate for 1–2 minutes at room temperature. Drain excess substrate, cover with plastic wrap, and image in digital CCD imager (auto-exposure series from 5 s to 3 min). Avoid signal saturation for quantitative densitometry.",
                temperature="Room temperature",
                duration="10–15 minutes",
                tip="If bands appear with white hollow centers ('ghost bands'), substrate burnout has occurred due to excessive protein/HRP; reload with lower protein mass or switch to lower-sensitivity ECL."
            ),
        ],
        troubleshooting=[
            TroubleshootingItem(
                issue="No bands visible (membrane is completely blank)",
                possible_cause="Reversed electrode polarity during transfer, sodium azide in HRP buffer, forgot PVDF methanol activation, or primary/secondary antibody species mismatch.",
                solution="Verify polarity (Negative/Black -> Gel -> Membrane -> Positive/Red); omit sodium azide from all secondary antibodies; activate PVDF in 100% methanol before use; verify secondary matches primary host species."
            ),
            TroubleshootingItem(
                issue="High dark background across the entire blot",
                possible_cause="Non-fat dry milk used to block phospho-specific antibody; secondary antibody concentration too high; insufficient washing; membrane dried out during handling.",
                solution="Switch to 5% BSA in TBST for phospho-targets; dilute secondary antibody to 1:10,000; perform at least 4 x 5 min TBST washes with vigorous shaking; keep membrane wet at all times."
            ),
            TroubleshootingItem(
                issue="White hollow centers surrounded by dark halos ('ghost bands' / substrate burnout)",
                possible_cause="Excessive protein loading (>30 µg) or ultra-high HRP activity rapidly exhausting the ECL luminol substrate at the band core.",
                solution="Reduce protein loading to 5–10 µg per lane; dilute secondary antibody 5-fold; switch from Femto ECL to standard Pico/Clarity ECL."
            ),
            TroubleshootingItem(
                issue="Target protein trapped in well or high-MW smear at top of gel",
                possible_cause="Multi-pass transmembrane protein (e.g. GluK2, AMPA receptors, GPCRs) aggregated upon high-temperature boiling at 95°C.",
                solution="Do NOT boil at 95°C. Denature lysates at 65°C–70°C for 10–15 minutes. Add 8 M urea if aggregation persists."
            ),
            TroubleshootingItem(
                issue="Patchy transfer with blank spots or swirl patterns",
                possible_cause="Air bubbles trapped between gel and membrane during cassette assembly; uneven cassette clamping pressure.",
                solution="Assemble transfer sandwich submerged in transfer buffer and roll out all bubbles with a blot roller before clamping."
            ),
        ],
        references=[
            "Towbin, H., Staehelin, T., & Gordon, J. (1979). Electrophoretic transfer of proteins from polyacrylamide gels to nitrocellulose sheets: procedure and some applications. Proceedings of the National Academy of Sciences, 76(9), 4350-4354.",
            "Burnette, W. N. (1981). 'Western blotting': electrophoretic transfer of proteins from sodium dodecyl sulfate-polyacrylamide gels to unmodified nitrocellulose and radiographic detection with antibody and radioiodinated protein A. Analytical Biochemistry, 112(2), 195-203.",
            "Taylor, S. C., & Posch, A. (2014). The design of a quantitative western blot experiment. Bio-Rad Laboratories White Paper, Bulletin 6570."
        ]
    ),
}


def list_protocols(category: Optional[str] = None) -> List[LabProtocol]:
    """Return all available protocols, optionally filtered by category."""
    if category:
        c_norm = category.lower().strip()
        return [p for p in PROTOCOL_CATALOG.values() if c_norm in p.category.lower()]
    return list(PROTOCOL_CATALOG.values())


def get_protocol(protocol_id: str) -> LabProtocol:
    """Retrieve a specific laboratory protocol by ID or substring."""
    p_id = protocol_id.lower().strip().replace("-", "_")
    if p_id in PROTOCOL_CATALOG:
        return PROTOCOL_CATALOG[p_id]
    for k, v in PROTOCOL_CATALOG.items():
        if p_id in k or p_id in v.title.lower():
            return v
    raise KeyError(f"Protocol '{protocol_id}' not found. Available: {list(PROTOCOL_CATALOG.keys())}")


def format_protocol_markdown(p: LabProtocol) -> str:
    """Format a LabProtocol object into a comprehensive markdown document."""
    lines = [
        f"# {p.title}",
        "",
        f"**Category:** {p.category}  |  **Estimated Time:** {p.estimated_time}  |  **Skill Level:** {p.skill_level}",
        "",
        "## 🔬 Overview & Purpose",
        p.summary,
        "",
        "## ⚠️ Safety & Handling Precautions",
    ]
    for s in p.safety_notes:
        lines.append(f"- **Caution:** {s}")

    lines.extend([
        "",
        "## 🧪 Reagents & Stock Solutions",
        "| Reagent Component | Working Concentration | Volume / Amount | Function & Bench Notes |",
        "| :--- | :--- | :--- | :--- |",
    ])
    for r in p.reagents:
        lines.append(f"| {r.name} | {r.concentration} | {r.amount_or_volume} | {r.notes} |")

    lines.extend([
        "",
        "## 🛠️ Materials & Equipment Required",
    ])
    for m in p.materials_equipment:
        lines.append(f"- {m}")

    lines.extend([
        "",
        "## 📋 Step-by-Step Bench Protocol",
    ])
    for s in p.steps:
        temp_dur = []
        if s.temperature:
            temp_dur.append(f"Temp: {s.temperature}")
        if s.duration:
            temp_dur.append(f"Time: {s.duration}")
        td_str = f" *({', '.join(temp_dur)})*" if temp_dur else ""

        lines.extend([
            f"### Step {s.step_number}: {s.title}{td_str}",
            s.instruction,
        ])
        if s.tip:
            lines.append(f"> **💡 Pro Tip:** {s.tip}")
        lines.append("")

    if p.troubleshooting:
        lines.extend([
            "## 🔍 Troubleshooting & Failure Analysis",
            "| Observation / Failure Mode | Root Cause | Corrective Action |",
            "| :--- | :--- | :--- |",
        ])
        for t in p.troubleshooting:
            lines.append(f"| **{t.issue}** | {t.possible_cause} | {t.solution} |")
        lines.append("")

    if p.references:
        lines.extend([
            "## 📚 Selected References & Citations",
        ])
        for idx, ref in enumerate(p.references, 1):
            lines.append(f"{idx}. {ref}")
        lines.append("")

    return "\n".join(lines)


def export_all_protocols_markdown(output_filepath: str) -> None:
    """Export all protocols in the catalog into a single consolidated reference markdown file."""
    md_blocks = [
        "# BioLabCalc Standard Laboratory Protocols Compendium 🧬🔬",
        "",
        "> A comprehensive collection of verified, benchmarked wet-lab molecular biology, RNA biochemistry, molecular cloning, and electrophoresis protocols.",
        "",
        "## Table of Contents",
        "",
    ]
    for idx, (p_id, p) in enumerate(PROTOCOL_CATALOG.items(), 1):
        md_blocks.append(f"{idx}. [{p.title}](#{p_id}) ({p.category})")
    md_blocks.append("\n---\n")

    for p_id, p in PROTOCOL_CATALOG.items():
        md_blocks.append(f"<a name=\"{p_id}\"></a>")
        md_blocks.append(format_protocol_markdown(p))
        md_blocks.append("\n---\n")

    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(md_blocks))
