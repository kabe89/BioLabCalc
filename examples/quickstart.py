"""Quickstart tutorial demonstrating BioLabCalc features across molecular biology, cloning, buffers, and protocols."""

import biolabcalc as blc
import biolabcalc.easy as easy

def main():
    print("=" * 75)
    print("  BIOLABCALC COMPREHENSIVE BENCH SCIENCE DEMO 🧬🔬")
    print("=" * 75)

    # 1. Molecular Weight Calculations
    print("\n1. MOLECULAR WEIGHT & STOICHIOMETRY")
    dna_seq = "ATGCCGTCCAGGCTGCTGGTC"
    dna_res = blc.calculate_dna_mw(dna_seq, double_stranded=True)
    print(f"Sequence: {dna_seq} (dsDNA, {dna_res.length} bp)")
    print(f"  MW: {dna_res.average_mw:,.2f} Da | GC: {dna_res.gc_content:.1f}%")

    moles, unit = blc.mass_to_moles(100.0, "ng", dna_res.average_mw)
    print(f"  100 ng = {moles:.2f} {unit}")

    # 2. In Vitro Transcription (IVT) Yield & Stoichiometry
    print("\n2. IN VITRO TRANSCRIPTION (IVT) ANALYSIS")
    rna_transcript = "GGGAGACCCAAGCUGGCCUGUGUGUACAGCCGAAUG"
    ivt_res = blc.calculate_ivt_yield(
        rna_seq=rna_transcript,
        reaction_volume_ul=20.0,
        measured_yield_ug=40.0,
        atp_mm=5.0, ctp_mm=5.0, gtp_mm=5.0, utp_mm=5.0,
        mg_conc_mm=20.0,
        template_dna_ng=500.0,
        template_dna_length_bp=3200,
    )
    print(f"RNA Length: {ivt_res.rna_length} nt (MW: {ivt_res.rna_mw:,.2f} Da)")
    print(f"  Synthesized: {ivt_res.rna_yield_ug} µg ({ivt_res.rna_yield_pmol:,.1f} pmol)")
    print(f"  Theoretical Max: {ivt_res.theoretical_max_yield_ug:.2f} µg (Limiting: {ivt_res.limiting_ntp})")
    print(f"  Efficiency: {ivt_res.overall_efficiency_percent:.1f}%")
    print(f"  Free Initial Mg2+: {ivt_res.free_mg_initial_mm:.1f} mM")
    print(f"  Pyrophosphate (PPi) released: {ivt_res.pyrophosphate_released_ug:.2f} µg ({ivt_res.pyrophosphate_released_nmol:.2f} nmol)")

    # 3. PCR Kinetics & dNTP Tracker
    print("\n3. PCR KINETICS & dNTP CONSUMPTION")
    pcr_res = blc.calculate_pcr_kinetics(
        amplicon_len_bp=650,
        template_ng=5.0,
        cycles=30,
        efficiency=0.98,
        reaction_volume_ul=50.0,
    )
    print(f"Amplicon Length: {pcr_res.amplicon_length_bp} bp (MW: {pcr_res.amplicon_mw:,.2f} Da)")
    print(f"  Initial Template Copies: {pcr_res.template_initial_copies:,.0f}")
    print(f"  Amplicon Yield: {pcr_res.amplicon_yield_ng:.2f} ng ({pcr_res.amplicon_yield_pmol:.3f} pmol)")
    print(f"  Limiting Reagent: {pcr_res.limiting_reagent} ({pcr_res.limiting_dntp})")

    # 4. Protein Quantification (A280 & A205)
    print("\n4. PROTEIN QUANTIFICATION")
    prot_seq = "MKWVTFISLLFLFSSAYSRGVFRRDTHKSEIAHRFKDLGE"
    prot_quant = blc.quantify_protein_a280(prot_seq, a280_absorbance=0.78, volume_ml=2.5)
    print(f"Protein: {prot_seq[:10]}... (MW: {prot_quant.molecular_weight:,.2f} Da)")
    print(f"  Concentration: {prot_quant.concentration_mg_ml:.3f} mg/mL ({prot_quant.molarity_um:.1f} µM)")
    print(f"  Total Yield: {prot_quant.total_yield_mg:.3f} mg ({prot_quant.total_yield_ug:,.1f} µg)")

    # 5. Restriction Digestion & Overhang Compatibility
    print("\n5. MOLECULAR CLONING & RESTRICTION DIGESTION")
    digest_plan = blc.plan_restriction_digest(
        dna_mass_ug=1.0,
        reaction_volume_ul=50.0,
        enzyme_1="EcoRI",
        enzyme_2="BamHI",
        dna_conc_ng_ul=200.0,
    )
    print(f"Enzymes: {digest_plan.enzyme_1.name} + {digest_plan.enzyme_2.name}")
    print(f"  Recommended Buffer: {digest_plan.recommended_buffer}")
    print(f"  Incubation: {digest_plan.incubation_temp_celsius}°C for {digest_plan.incubation_time_min} min")
    compat, note = blc.are_overhangs_compatible("BamHI", "BglII")
    print(f"  BamHI / BglII Overhang Check: {note}")

    # 6. Gibson Isothermal Assembly
    print("\n6. GIBSON ASSEMBLY STOICHIOMETRY")
    gibson_plan = blc.calculate_gibson_assembly(
        vector_length_bp=4500,
        insert_lengths_bp=[1200, 800],
        vector_mass_ng=100.0,
        molar_ratio=2.0,
    )
    print(f"Vector (4500 bp): 100.0 ng ({gibson_plan.reagent_volumes['Linearized Vector (100.0 ng)']} µL)")
    print(f"  Total DNA Input: {gibson_plan.total_dna_pmol:.3f} pmol")
    print(f"  Protocol: {gibson_plan.incubation_protocol}")

    # 7. Laboratory Buffer Recipes & Tris Temperature Compensation
    print("\n7. LABORATORY BUFFERS & TEMPERATURE COMPENSATION")
    buffer_recipe = blc.calculate_buffer_recipe("10X_PBS", target_volume_ml=500.0)
    print(f"Recipe for {buffer_recipe.name} (500 mL):")
    for comp in buffer_recipe.components:
        print(f"  - {comp.name}: {comp.amount} {comp.unit} [{comp.molar_concentration}]")
    shifted_ph = blc.calculate_tris_temperature_shift(measured_ph=8.00, measured_temp_c=25.0, target_temp_c=4.0)
    print(f"  Tris Buffer (pH 8.00 at 25°C) -> Expected in Cold Room (4°C): pH {shifted_ph}")

    # 8. NTP Neutralization & pH Adjustment
    print("\n8. NTP SOLUTION NEUTRALIZATION & pH ADJUSTMENT")
    ntp_adj = blc.calculate_ntp_ph_adjustment(
        initial_volume_ml=4.0,
        initial_conc_mm=100.0,
        target_volume_ml=16.0,
        target_conc_mm=25.0,
        starting_form="disodium_salt",
    )
    print(f"4 mL of 100 mM NTPs -> 16 mL of 25 mM NTPs (pH 7.5):")
    print(f"  5 M NaOH required: {ntp_adj.naoh_volume_ul['5M']} µL")
    print(f"  Diluent water: ~{ntp_adj.water_volume_ml:.2f} mL (bring to 16.0 mL mark)")

    # 9. Easy Universal Dilution (C1*V1 = C2*V2)
    print("\n9. EASY ONE-LINE DILUTION CALCULATOR")
    dilution_res = easy.dilute(c1="100 mM", c2="25 mM", v2="16 mL")
    print(f"Dilution solution: Take {dilution_res['v1']/1000.0:.2f} mL stock and add {dilution_res['diluent_needed']/1000.0:.2f} mL diluent.")

    # 10. Protocols Compendium
    print("\n10. STANDARD LABORATORY PROTOCOLS")
    proto = blc.get_protocol("ntp_neutralization")
    print(f"Protocol: {proto.title} ({proto.category})")
    print(f"  Estimated Time: {proto.estimated_time} | Skill Level: {proto.skill_level}")
    print(f"  Number of Steps: {len(proto.steps)} | Troubleshooting Entries: {len(proto.troubleshooting)}")

    # 11. Golden Gate Assembly (Type IIS Cloning)
    print("\n11. GOLDEN GATE ASSEMBLY SETUP (BsaI-HFv2)")
    gg_res = easy.golden_gate(vector_bp=4500, insert_bps=[1200, 600], target_fmol=20.0, enzyme="BsaI-HFv2")
    print(f"Destination Vector ({gg_res.vector_length_bp} bp): {gg_res.vector_mass_ng:.1f} ng ({gg_res.vector_fmol:.1f} fmol)")
    for idx, (ins_len, ins_m, ins_f) in enumerate(zip(gg_res.insert_lengths_bp, gg_res.insert_masses_ng, gg_res.insert_fmols), 1):
        print(f"  Insert #{idx} ({ins_len} bp): {ins_m:.1f} ng ({ins_f:.1f} fmol)")
    print(f"Thermocycling: {gg_res.thermocycling_protocol[0]}")

    # 12. NanoDrop Nucleic Acid Purity Assessment
    print("\n12. NANODROP PURITY & CONTAMINANT ASSESSMENT")
    purity_res = easy.nanodrop_purity(a260=1.25, a280=0.63, a230=0.58, sample_type="rna")
    print(f"Readings: A260={purity_res.a260}, A280={purity_res.a280}, A230={purity_res.a230}")
    print(f"Ratios: A260/A280 = {purity_res.a260_a280_ratio:.2f} | A260/A230 = {purity_res.a260_a230_ratio:.2f}")
    print(f"Status: {purity_res.purity_status.upper()} -> {purity_res.diagnostic_feedback[0]}")

    # 13. Phenol:Chloroform Extraction Protocol
    print("\n13. PHENOL:CHLOROFORM PHASE SEPARATION EXTRACTION")
    pci_res = easy.phenol_chloroform("150 uL", nucleic_acid="rna")
    print(f"Grade: {pci_res.phenol_type}")
    print(f"Aqueous Phase: {pci_res.aqueous_phase_layer}")
    print(f"Recipe: 150 µL Sample + {pci_res.pci_volume_ul:.1f} µL PCI + {pci_res.chloroform_volume_ul:.1f} µL Chloroform back-extraction")

    # 14. IVT with Promoter Trimming & N1-Methylpseudouridine (m1Ψ)
    print("\n14. IVT WITH PROMOTER AUTO-TRIMMING & MODIFIED NUCLEOTIDES (m1Ψ)")
    ivt_mod = blc.calculate_ivt_yield(
        rna_seq="TAATACGACTCACTATAGGGAGACCCAAGCUGGCC",
        reaction_volume_ul=20.0,
        measured_yield_ug=40.0,
        auto_trim_promoter=True,
        add_5prime_gg=2,
        modified_ntp="m1Psi",
        cap_analog="CleanCap_AG",
    )
    print(f"Transcribed Sequence Length: {ivt_mod.rna_length} nt (Promoter Trimmed: {ivt_mod.promoter_detected})")
    print(f"Modified RNA MW (m1Ψ + CleanCap): {ivt_mod.rna_mw:,.2f} Da (Initiation: {ivt_mod.initiation_efficiency_rating})")
    print(f"Estimated Capping Efficiency: {ivt_mod.predicted_capping_efficiency_percent:.0f}%")

    print("\n" + "=" * 75)
    print("  ALL 14 DEMONSTRATION WORKFLOWS COMPLETED SUCCESSFULLY! ✨")
    print("=" * 75)

if __name__ == "__main__":
    main()
