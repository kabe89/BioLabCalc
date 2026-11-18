"""
Script: scripts/build_pages_demo.py
Purpose: Build static GitHub Pages interactive live demo portal and documentation site.
Outputs:
  - docs_site/index.html (Main portal landing page)
  - docs_site/plasmid.html (Interactive Plasmid Workbench)
  - docs_site/gel.html (Interactive Agarose/PAGE Gel Simulator)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# Ensure 'src' is in pythonpath
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from biolabcalc import __version__
from biolabcalc.interactive_gel import get_interactive_html
from biolabcalc.interactive_plasmid import get_plasmid_workbench_html


def build_pages_demo(output_dir: Optional[Path] = None) -> Path:
    if output_dir is None:
        output_dir = repo_root / "docs_site"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate standalone Plasmid Workbench
    plasmid_html = get_plasmid_workbench_html()
    (output_dir / "plasmid.html").write_text(plasmid_html, encoding="utf-8")

    # 2. Generate standalone Gel Simulator
    gel_html = get_interactive_html()
    (output_dir / "gel.html").write_text(gel_html, encoding="utf-8")

    # 3. Generate Main Landing Page (index.html)
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BioLabCalc v{__version__} — Pure-Python Molecular Biology & Biophysics Suite</title>
    <meta name="description" content="Pure-Python molecular biology and biophysical calculation suite with zero mandatory dependencies. 45 CLI tools, Bio-Rad .scn/.1sc parser, ELN & LIMS pipeline, microplate liquid handling automation.">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🧬</text></svg>">
    <style>
        :root {{
            --primary: #2563EB;
            --primary-dark: #1D4ED8;
            --bg: #F8FAFC;
            --card-bg: #FFFFFF;
            --text-main: #0F172A;
            --text-muted: #64748B;
            --border: #E2E8F0;
            --accent: #10B981;
            --font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: var(--font-sans);
            background: var(--bg);
            color: var(--text-main);
            line-height: 1.6;
        }}
        header {{
            background: #0F172A;
            color: #FFFFFF;
            padding: 3rem 1.5rem 2.5rem;
            text-align: center;
            border-bottom: 3px solid var(--primary);
        }}
        .badge {{
            display: inline-block;
            background: rgba(37, 99, 235, 0.2);
            color: #60A5FA;
            border: 1px solid rgba(96, 165, 250, 0.3);
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            margin-bottom: 1rem;
            letter-spacing: 0.05em;
        }}
        h1 {{
            font-size: 2.75rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            margin-bottom: 0.75rem;
        }}
        .tagline {{
            font-size: 1.25rem;
            color: #94A3B8;
            max-width: 750px;
            margin: 0 auto 1.75rem;
        }}
        .hero-actions {{
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            font-size: 0.95rem;
        }}
        .btn-primary {{
            background: var(--primary);
            color: #FFFFFF;
        }}
        .btn-primary:hover {{ background: var(--primary-dark); }}
        .btn-secondary {{
            background: #1E293B;
            color: #E2E8F0;
            border: 1px solid #334155;
        }}
        .btn-secondary:hover {{ background: #334155; }}

        main {{
            max-width: 1200px;
            margin: 2.5rem auto;
            padding: 0 1.5rem;
        }}

        .features-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.75rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.08);
        }}
        .card h3 {{
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .card p {{
            font-size: 0.95rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
        }}
        .card a {{
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
        }}

        .demo-section {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 3rem;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }}
        .demo-tabs {{
            display: flex;
            gap: 0.5rem;
            border-bottom: 2px solid var(--border);
            margin-bottom: 1.5rem;
        }}
        .tab-btn {{
            padding: 0.75rem 1.25rem;
            font-size: 1rem;
            font-weight: 600;
            background: none;
            border: none;
            border-bottom: 3px solid transparent;
            color: var(--text-muted);
            cursor: pointer;
            margin-bottom: -2px;
        }}
        .tab-btn.active {{
            color: var(--primary);
            border-bottom-color: var(--primary);
        }}
        .demo-frame {{
            width: 100%;
            height: 750px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: #FFFFFF;
        }}

        .code-block {{
            background: #0F172A;
            color: #F8FAFC;
            padding: 1.25rem;
            border-radius: 8px;
            font-family: var(--font-mono);
            font-size: 0.9rem;
            overflow-x: auto;
            margin: 1.5rem 0;
        }}

        footer {{
            text-align: center;
            padding: 3rem 1.5rem;
            color: var(--text-muted);
            font-size: 0.9rem;
            border-top: 1px solid var(--border);
            background: #FFFFFF;
        }}
    </style>
</head>
<body>
    <header>
        <span class="badge">VERSION {__version__} RELEASE</span>
        <h1>BioLabCalc</h1>
        <p class="tagline">The Zero-Dependency Pure-Python Molecular Biology, Biophysics & Laboratory Automation Suite</p>
        <div class="hero-actions">
            <a href="#live-demos" class="btn btn-primary">Explore Live Apps</a>
            <a href="https://github.com/kabe89/BioLabCalc" target="_blank" class="btn btn-secondary">GitHub Repository</a>
            <a href="https://github.com/kabe89/BioLabCalc/wiki" target="_blank" class="btn btn-secondary">Documentation Wiki</a>
        </div>
    </header>

    <main>
        <div class="code-block">
            # Pure Python Stdlib Core — Zero mandatory third-party dependencies<br>
            pip install biolabcalc
        </div>

        <section class="features-grid">
            <div class="card">
                <h3>🧪 Multi-Metal Buffer Speciation</h3>
                <p>Newton-Raphson log-space solver evaluating competitive divalent cation chelation (Mg²⁺, Ca²⁺, ATP, EGTA, EDTA) with Davies activity and temperature drift.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/09-Wet-Lab-Buffer-Preparation-Guide" target="_blank">Buffer Documentation →</a>
            </div>
            <div class="card">
                <h3>🧬 Subunit Aptamer Counter-SELEX</h3>
                <p>Turner (2004) nearest-neighbor RNA hairpin thermodynamics paired with Dirichlet-smoothed Counter-SELEX sequencing enrichment and Benjamini-Hochberg FDR.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/04-Aptamer-Design-and-SELEX-Analytics" target="_blank">Aptamer Guide →</a>
            </div>
            <div class="card">
                <h3>🔍 Allosteric Pathway Tracing</h3>
                <p>Gaussian Network Model (GNM) Kirchhoff Laplacian solver and Perturbation Response Scanning (PRS) tracing dynamic allosteric networks and mutagenic primers.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/07-Allostery-and-Dynamics-Modeling" target="_blank">Allostery Guide →</a>
            </div>
            <div class="card">
                <h3>🤖 Microplate Liquid Handling</h3>
                <p>Automated 96/384-well serial dilutions, PCR master-mix setups, and direct protocol compilation for Labcyte Echo, Opentrons OT-2/Flex, and PyLabRobot.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/10-Microplate-Automation-and-Liquid-Handling" target="_blank">Automation Guide →</a>
            </div>
            <div class="card">
                <h3>📁 Open Sequence Interoperability</h3>
                <p>Pure-Python parsers for SnapGene binary (.dna), Sanger sequencing traces (.ab1 with Ediacara verification), and RO-Crate (.eln) compliant research bundles.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/03-Plasmid-Maps-and-Cloning" target="_blank">Cloning Guide →</a>
            </div>
            <div class="card">
                <h3>📊 Jupyter Rich Representations</h3>
                <p>Interactive vector SVG circular plasmid maps and gel lane diagrams (_repr_svg_) plus styled analytical report cards (_repr_html_) inside notebooks.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/02-Calculations-Reference" target="_blank">Jupyter Guide →</a>
            </div>
        </section>

        <section id="live-demos" class="demo-section">
            <h2 style="font-size: 1.75rem; margin-bottom: 0.5rem;">Interactive Live Web Applications</h2>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem;">Run standalone client-side SVG plasmid maps and gel electrophoresis simulations directly in your browser.</p>

            <div class="demo-tabs">
                <button class="tab-btn active" onclick="switchTab('plasmid')">Interactive Plasmid Workbench</button>
                <button class="tab-btn" onclick="switchTab('gel')">Agarose & PAGE Gel Simulator</button>
            </div>

            <iframe id="demoFrame" class="demo-frame" src="plasmid.html" title="BioLabCalc Interactive Demo"></iframe>
        </section>
    </main>

    <footer>
        <p>BioLabCalc v{__version__} — Licensed under MIT. Developed by kabe89 & the Open Source Life Sciences Community.</p>
        <p style="margin-top: 0.5rem; font-size: 0.85rem;">Designed for production research environments, high-throughput screening, and automated workflows.</p>
    </footer>

    <script>
        function switchTab(demo) {{
            const btns = document.querySelectorAll('.tab-btn');
            btns.forEach(b => b.classList.remove('active'));
            const frame = document.getElementById('demoFrame');
            if (demo === 'plasmid') {{
                btns[0].classList.add('active');
                frame.src = 'plasmid.html';
            }} else {{
                btns[1].classList.add('active');
                frame.src = 'gel.html';
            }}
        }}
    </script>
</body>
</html>
"""
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    return output_dir


if __name__ == "__main__":
    out = build_pages_demo()
    print(f"Successfully generated GitHub Pages demo portal at: {out}")
