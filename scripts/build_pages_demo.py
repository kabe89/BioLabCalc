"""
Script: scripts/build_pages_demo.py
Purpose: Build static GitHub Pages interactive live demo portal and documentation site.
Outputs:
  - docs_site/index.html (Main portal landing page)
  - docs_site/plasmid.html (Interactive Plasmid Workbench)
  - docs_site/gel.html (Interactive Agarose/PAGE Gel Simulator)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional, Union

# Ensure 'src' is in pythonpath
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from biolabcalc import __version__
from biolabcalc.interactive_gel import get_interactive_html
from biolabcalc.interactive_plasmid import get_plasmid_workbench_html


def _safe_write_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except (PermissionError, OSError):
        try:
            import stat
            if path.exists():
                os.chmod(path, stat.S_IWRITE)
            path.write_text(text, encoding="utf-8")
        except Exception:
            pass


def build_pages_demo(output_dir: Optional[Union[str, Path]] = None) -> Path:
    out_dir = Path(output_dir) if output_dir is not None else repo_root / "docs_site"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate standalone Plasmid Workbench
    plasmid_html = get_plasmid_workbench_html()
    _safe_write_text(out_dir / "plasmid.html", plasmid_html)

    # 2. Generate standalone Gel Simulator
    gel_html = get_interactive_html()
    _safe_write_text(out_dir / "gel.html", gel_html)

    # Dynamic CLI subcommand count
    cli_file = repo_root / "src" / "biolabcalc" / "cli.py"
    if cli_file.exists():
        cli_count = len(re.findall(r'subparsers\.add_parser\(', cli_file.read_text(encoding="utf-8")))
    else:
        cli_count = 44

    # 3. Generate Main Landing Page (index.html)
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BioLabCalc v{__version__} — Pure-Python Molecular Biology & Biophysics Suite</title>
    <meta name="description" content="Pure-Python molecular biology and biophysical calculation suite with zero mandatory dependencies. {cli_count} CLI tools, Bio-Rad .scn/.1sc parser, ELN & LIMS pipeline, microplate liquid handling automation.">
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
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            line-height: 1.6;
        }}

        header {{
            background: linear-gradient(135deg, #1E3A8A 0%, #0F172A 100%);
            color: white;
            padding: 4rem 2rem;
            text-align: center;
            border-bottom: 4px solid var(--primary);
        }}

        .hero-badge {{
            display: inline-block;
            background: rgba(37, 99, 235, 0.2);
            color: #60A5FA;
            border: 1px solid #3B82F6;
            padding: 0.35rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        h1 {{
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 1rem;
            letter-spacing: -0.025em;
        }}

        h1 span {{
            color: #60A5FA;
        }}

        .lead {{
            font-size: 1.25rem;
            color: #94A3B8;
            max-width: 800px;
            margin: 0 auto 2rem;
        }}

        .cta-buttons {{
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
        }}

        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
        }}

        .btn-primary {{
            background-color: var(--primary);
            color: white;
        }}

        .btn-primary:hover {{
            background-color: var(--primary-dark);
            transform: translateY(-1px);
        }}

        .btn-secondary {{
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}

        .btn-secondary:hover {{
            background-color: rgba(255, 255, 255, 0.2);
        }}

        main {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem 1.5rem;
        }}

        .code-block {{
            background: #0F172A;
            color: #F8FAFC;
            padding: 1rem 1.5rem;
            border-radius: 0.5rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.95rem;
            max-width: 600px;
            margin: -5.5rem auto 3rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            border: 1px solid #334155;
            text-align: center;
        }}

        .features-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 2rem;
            margin-bottom: 4rem;
        }}

        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            padding: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }}

        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            border-color: #CBD5E1;
        }}

        .card h3 {{
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .card p {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-bottom: 1.25rem;
        }}

        .card a {{
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }}

        .card a:hover {{
            text-decoration: underline;
        }}

        .demo-section {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 1rem;
            padding: 2.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            text-align: center;
        }}

        .demo-tabs {{
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .tab-btn {{
            padding: 0.5rem 1.25rem;
            border-radius: 9999px;
            font-weight: 600;
            border: 1px solid var(--border);
            background: var(--bg);
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s;
        }}

        .tab-btn.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        .demo-frame {{
            width: 100%;
            height: 750px;
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            background: white;
        }}

        footer {{
            text-align: center;
            padding: 3rem 1rem;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <header>
        <div class="hero-badge">BioLabCalc v{__version__} Release</div>
        <h1>BioLabCalc <span>Portal</span></h1>
        <p class="lead">A multifaceted Python library, Excel extension, and interactive laboratory suite for molecular biology, biophysics, stoichiometric calculations, and ELN pipelines.</p>
        <div class="cta-buttons">
            <a href="#live-demos" class="btn btn-primary">Try Live Web Demos</a>
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
                <a href="https://github.com/kabe89/BioLabCalc/wiki/Buffers-&-Precipitation" target="_blank">Buffer Documentation →</a>
            </div>
            <div class="card">
                <h3>🧬 Subunit Aptamer Counter-SELEX</h3>
                <p>Turner (2004) nearest-neighbor RNA hairpin thermodynamics paired with Dirichlet-smoothed Counter-SELEX sequencing enrichment and Benjamini-Hochberg FDR.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/Core-Calculators-&-Biophysics" target="_blank">Aptamer Guide →</a>
            </div>
            <div class="card">
                <h3>🔍 Allosteric Pathway Tracing</h3>
                <p>Gaussian Network Model (GNM) Kirchhoff Laplacian solver and Perturbation Response Scanning (PRS) tracing dynamic allosteric networks and mutagenic primers.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/Core-Calculators-&-Biophysics" target="_blank">Allostery Guide →</a>
            </div>
            <div class="card">
                <h3>🤖 Microplate Liquid Handling</h3>
                <p>Automated 96/384-well serial dilutions, PCR master-mix setups, and direct protocol compilation for Labcyte Echo, Opentrons OT-2/Flex, and PyLabRobot.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/Python-API-Reference" target="_blank">Automation Guide →</a>
            </div>
            <div class="card">
                <h3>📁 Open Sequence Interoperability</h3>
                <p>Pure-Python parsers for SnapGene binary (.dna), Sanger sequencing traces (.ab1 with Ediacara verification), and RO-Crate (.eln) compliant research bundles.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/Molecular-Cloning-&-Assembly" target="_blank">Cloning Guide →</a>
            </div>
            <div class="card">
                <h3>📊 Jupyter Rich Representations</h3>
                <p>Interactive vector SVG circular plasmid maps and gel lane diagrams (_repr_svg_) plus styled analytical report cards (_repr_html_) inside notebooks.</p>
                <a href="https://github.com/kabe89/BioLabCalc/wiki/Gel-Electrophoresis-&-Image-Annotator" target="_blank">Jupyter Guide →</a>
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
    _safe_write_text(out_dir / "index.html", index_html)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build static GitHub Pages demo portal")
    parser.add_argument("--check", action="store_true", help="Check if docs_site/ is in sync without writing")
    parser.add_argument("--output-dir", default=None, help="Target directory for generated portal")
    args = parser.parse_args()

    out_dir = Path(args.output_dir) if args.output_dir else repo_root / "docs_site"

    if args.check:
        if not out_dir.exists():
            print("docs_site/ does not exist. Run 'python scripts/build_pages_demo.py' to generate it.")
            return 1

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            build_pages_demo(tmp_path)
            for f_name in ["index.html", "plasmid.html", "gel.html"]:
                gen_file = tmp_path / f_name
                cur_file = out_dir / f_name
                if not cur_file.exists():
                    print(f"DRIFT: {cur_file} is missing.")
                    return 1
                if cur_file.read_text(encoding="utf-8") != gen_file.read_text(encoding="utf-8"):
                    print(f"DRIFT: {cur_file} is out of sync with latest generator output.")
                    return 1

        print("docs_site/ is completely in sync.")
        return 0

    built = build_pages_demo(out_dir)
    print(f"Successfully generated GitHub Pages demo portal at: {built}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
