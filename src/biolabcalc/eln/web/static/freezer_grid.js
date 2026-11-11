/**
 * @file freezer_grid.js
 * @agent eln-frontend-agent
 * @description Interactive 2D Freezer Box Grid (9x9 and 10x10) & Sample Lineage Tracking Visualizer.
 * @architecture Manages hierarchical cryogenic storage topologies (-80°C Vaults, Racks, Shelves, Boxes),
 *               renders dynamic CSS Grid / Canvas 2D tube visualizers, handles slot hover tooltips,
 *               and drives the slide-out Sample Provenance Lineage Drawer connecting daily entries,
 *               FPLC fraction pools, NanoDrop QC spectra, and gel lanes.
 */

/**
 * Represents a stored cryogenic tube in the LIMS database.
 * @typedef {Object} LimsTube
 * @property {string} tubeId - Unique barcode identifier (e.g., 'TUB-2026-T7-042')
 * @property {string} boxPosition - Well coordinate (e.g., 'C4')
 * @property {string} sampleName - Human-readable sample name
 * @property {string} sampleType - Sample type category ('protein', 'plasmid', 'primer', 'glycerol', 'buffer')
 * @property {number} concentration - Concentration numeric value
 * @property {string} concentrationUnits - Units (e.g., 'mg/mL', 'ng/µL', 'µM')
 * @property {number} volumeUl - Remaining liquid volume in microliters
 * @property {number} freezeThawCycles - Number of recorded freeze-thaw cycles
 * @property {number} maxFreezeThaw - Maximum recommended freeze-thaw cycles
 * @property {string} storageTemp - Temperature specification (e.g., '-80°C')
 * @property {string} dateStored - ISO timestamp of initial storage
 * @property {string} operator - Researcher name
 * @property {Object} lineage - Provenance metadata
 * @property {string} [lineage.campaignId] - Originating experimental campaign
 * @property {string} [lineage.dailyEntry] - Originating notebook entry
 * @property {string} [lineage.fplcPoolId] - Source FPLC fraction pool
 * @property {string} [lineage.nanoDropId] - Source QC NanoDrop spectrum
 * @property {string} [lineage.gelLaneId] - Source SDS-PAGE gel lane
 * @property {string} [lineage.constructId] - Source plasmid construct
 */

/**
 * FreezerGrid Class: Coordinates 2D box grid rendering, slot interactions, and lineage cards.
 * @agent eln-frontend-agent
 * @role Cryogenic storage LIMS component
 */
export class FreezerGrid {
  /**
   * Initializes the FreezerGrid instance.
   * @agent eln-frontend-agent
   * @role Component Constructor
   * @param {string|HTMLElement} containerElement - Container element or ID for grid rendering
   * @param {Object} options - Configuration options
   * @param {string} [options.boxDimensions='9x9'] - Box dimension ('9x9' or '10x10')
   * @param {string|HTMLElement} [options.drawerElement] - Tube lineage drawer element
   * @param {Function} [options.onTubeSelected] - Callback triggered when a tube slot is clicked
   */
  constructor(containerElement, options = {}) {
    this.container = typeof containerElement === 'string' ? document.getElementById(containerElement) : containerElement;
    if (!this.container) {
      throw new Error(`[FreezerGrid] Container element not found: ${containerElement}`);
    }
    this.drawer = options.drawerElement
      ? (typeof options.drawerElement === 'string' ? document.getElementById(options.drawerElement) : options.drawerElement)
      : null;

    this.options = Object.assign({
      boxDimensions: '9x9', // '9x9' (81 wells: A1-I9) or '10x10' (100 wells: A1-J10)
      activeBoxId: 'BOX-B-07',
      onTubeSelected: null
    }, options);

    // Current Active Box Topology
    this.activeBox = {
      id: 'BOX-B-07',
      name: 'T7 RNAP Purification & Aliquots 2026',
      locationPath: '-80°C Cryo-Vault Alpha > Rack R-02 > Shelf S-3 > Box B-07',
      dimensions: this.options.boxDimensions,
      tubes: new Map() // Key: coordinate like 'C4'
    };

    // Populate Initial T7 RNA Polymerase Campaign Aliquots
    this._populateInitialTubes();
    this.render();
  }

  /**
   * Populates default aliquots from the T7 RNA Polymerase 5-Day Campaign.
   * @agent eln-frontend-agent
   * @role Synthetic Inventory Population
   * @private
   * @returns {void}
   */
  _populateInitialTubes() {
    this.activeBox.tubes.clear();

    // 1. T7 RNAP Purified Aliquots (Pool B4-B8, 50 µL each @ 3.85 mg/mL) in Wells C1 through C8
    for (let col = 1; col <= 8; col++) {
      const coord = `C${col}`;
      this.activeBox.tubes.set(coord, {
        tubeId: `TUB-2026-T7-04${col}`,
        boxPosition: coord,
        sampleName: `T7 RNAP His6 - Pool B4-B8 Aliquot #${col}`,
        sampleType: 'protein',
        concentration: 3.85,
        concentrationUnits: 'mg/mL',
        volumeUl: 50,
        freezeThawCycles: 1,
        maxFreezeThaw: 5,
        storageTemp: '-80°C',
        dateStored: '2026-10-28',
        operator: 'Dr. Elena Rostova',
        lineage: {
          campaignId: 'CAMP-2026-T7RNAP',
          campaignName: '5-Day T7 RNA Polymerase High-Yield Expression',
          dailyEntry: 'Day 4: Size Exclusion & Final Formulation',
          fplcPoolId: 'POOL-B4-B8 (5.0 mL, 19.25 mg yield)',
          nanoDropId: 'ND-2026-0881 (A280=5.39, A260/A280=0.58)',
          gelLaneId: 'GEL-2026-044 Lane 8 (MW: 98.9 kDa, >98% purity)',
          constructId: 'pET-28a-T7RNAP (KanR, T7 promoter)',
          buffer: '50 mM Tris-HCl pH 7.9, 100 mM NaCl, 1 mM DTT, 0.1 mM EDTA, 50% Glycerol'
        }
      });
    }

    // 2. Expression Plasmid Minipreps in Wells A1, A2
    this.activeBox.tubes.set('A1', {
      tubeId: 'TUB-2026-PLAS-001',
      boxPosition: 'A1',
      sampleName: 'pET-28a-T7RNAP Working Stock',
      sampleType: 'plasmid',
      concentration: 245.0,
      concentrationUnits: 'ng/µL',
      volumeUl: 40,
      freezeThawCycles: 2,
      maxFreezeThaw: 10,
      storageTemp: '-20°C',
      dateStored: '2026-10-24',
      operator: 'Dr. Elena Rostova',
      lineage: {
        campaignId: 'CAMP-2026-T7RNAP',
        dailyEntry: 'Day 0: Plasmid Prep & Quality Verification',
        nanoDropId: 'ND-2026-0870 (A260/A280 = 1.88)',
        constructId: 'pET-28a-T7RNAP',
        buffer: '10 mM Tris-HCl pH 8.0, 0.1 mM EDTA'
      }
    });

    // 3. Forward & Reverse Primers in Wells B1, B2
    this.activeBox.tubes.set('B1', {
      tubeId: 'TUB-2026-PRM-01',
      boxPosition: 'B1',
      sampleName: 'T7-Promoter-Fwd (100 µM)',
      sampleType: 'primer',
      concentration: 100.0,
      concentrationUnits: 'µM',
      volumeUl: 85,
      freezeThawCycles: 3,
      maxFreezeThaw: 15,
      storageTemp: '-20°C',
      dateStored: '2026-10-20',
      operator: 'Dr. Elena Rostova',
      lineage: {
        constructId: 'pET-28a-T7RNAP',
        sequence: "5'-TAATACGACTCACTATAGGG-3'"
      }
    });

    // 4. Glycerol Stocks in Wells D1, D2
    this.activeBox.tubes.set('D1', {
      tubeId: 'TUB-2026-GLYC-01',
      boxPosition: 'D1',
      sampleName: 'BL21(DE3) [pET-28a-T7RNAP] Master Stock',
      sampleType: 'glycerol',
      concentration: 1.0,
      concentrationUnits: 'OD600 equivalent',
      volumeUl: 800,
      freezeThawCycles: 0,
      maxFreezeThaw: 2,
      storageTemp: '-80°C',
      dateStored: '2026-10-25',
      operator: 'Dr. Elena Rostova',
      lineage: {
        campaignId: 'CAMP-2026-T7RNAP',
        dailyEntry: 'Day 1: Transformation & Primary Outgrowth',
        constructId: 'pET-28a-T7RNAP'
      }
    });
  }

  /**
   * Renders the 2D visual box grid into the DOM.
   * @agent eln-frontend-agent
   * @role DOM Visual Grid Builder
   * @returns {void}
   */
  render() {
    this.container.innerHTML = '';

    const is10x10 = this.options.boxDimensions === '10x10';
    const rowLetters = is10x10
      ? ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
      : ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'];
    const colCount = is10x10 ? 10 : 9;

    const gridWrapper = document.createElement('div');
    gridWrapper.className = `box-grid-container ${is10x10 ? 'box-grid-10x10' : 'box-grid-9x9'}`;

    for (const row of rowLetters) {
      for (let col = 1; col <= colCount; col++) {
        const coord = `${row}${col}`;
        const slotEl = document.createElement('div');
        slotEl.className = 'grid-cell-slot';
        slotEl.dataset.coord = coord;
        slotEl.textContent = coord;

        const tube = this.activeBox.tubes.get(coord);
        if (tube) {
          slotEl.classList.add(`type-${tube.sampleType}`);
          slotEl.title = `${coord}: ${tube.sampleName} (${tube.concentration} ${tube.concentrationUnits})`;
        } else {
          slotEl.title = `${coord}: Empty Well`;
        }

        slotEl.addEventListener('click', () => this._handleSlotClick(coord));
        gridWrapper.appendChild(slotEl);
      }
    }

    this.container.appendChild(gridWrapper);
  }

  /**
   * Handles user click on a tube well slot.
   * @agent eln-frontend-agent
   * @role Slot Click Dispatcher
   * @private
   * @param {string} coord - Well coordinate (e.g., 'C4')
   * @returns {void}
   */
  _handleSlotClick(coord) {
    const tube = this.activeBox.tubes.get(coord);
    if (!tube) {
      // Empty slot clicked
      if (this.drawer) {
        this.drawer.classList.remove('open');
      }
      return;
    }

    if (typeof this.options.onTubeSelected === 'function') {
      this.options.onTubeSelected(tube);
    }

    if (this.drawer) {
      this.displayTubeLineage(tube);
    }
  }

  /**
   * Displays full provenance lineage in the slide-out drawer.
   * @agent eln-frontend-agent
   * @role Lineage Drawer Visualizer
   * @param {LimsTube} tube - Target tube record
   * @returns {void}
   */
  displayTubeLineage(tube) {
    if (!this.drawer) return;

    const drawerBody = this.drawer.querySelector('.drawer-body');
    const drawerTitle = this.drawer.querySelector('.drawer-title');

    if (drawerTitle) {
      drawerTitle.textContent = `${tube.boxPosition} • ${tube.sampleName}`;
    }

    if (drawerBody) {
      drawerBody.innerHTML = `
        <div style="margin-bottom: 16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span class="badge badge-info" style="font-size:0.8rem;">${tube.sampleType.toUpperCase()}</span>
            <span style="font-family:var(--font-mono); font-size:0.8rem; color:var(--text-muted);">${tube.tubeId}</span>
          </div>
          <div style="font-size:1.15rem; font-weight:700; color:var(--text-primary); margin-bottom:4px;">
            ${tube.sampleName}
          </div>
          <div style="font-size:0.85rem; color:var(--text-muted);">${this.activeBox.locationPath} • Well <strong>${tube.boxPosition}</strong></div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:20px;">
          <div style="background:var(--bg-app); padding:10px; border-radius:6px; border:1px solid var(--border);">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase;">Concentration</div>
            <div style="font-size:1.1rem; font-weight:700; font-family:var(--font-mono); color:var(--accent);">
              ${tube.concentration} ${tube.concentrationUnits}
            </div>
          </div>
          <div style="background:var(--bg-app); padding:10px; border-radius:6px; border:1px solid var(--border);">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase;">Remaining Volume</div>
            <div style="font-size:1.1rem; font-weight:700; font-family:var(--font-mono); color:var(--text-primary);">
              ${tube.volumeUl} µL
            </div>
          </div>
          <div style="background:var(--bg-app); padding:10px; border-radius:6px; border:1px solid var(--border);">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase;">Freeze-Thaw Cycles</div>
            <div style="font-size:1.1rem; font-weight:700; font-family:var(--font-mono); color:${tube.freezeThawCycles >= tube.maxFreezeThaw ? 'var(--fail)' : 'var(--pass)'};">
              ${tube.freezeThawCycles} / ${tube.maxFreezeThaw} max
            </div>
          </div>
          <div style="background:var(--bg-app); padding:10px; border-radius:6px; border:1px solid var(--border);">
            <div style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase;">Storage Condition</div>
            <div style="font-size:1.1rem; font-weight:700; font-family:var(--font-mono); color:var(--text-primary);">
              ${tube.storageTemp}
            </div>
          </div>
        </div>

        <h4 style="font-size:0.9rem; font-weight:700; margin-bottom:12px; color:var(--text-primary); border-bottom:1px solid var(--border); padding-bottom:6px;">
          Experimental Lineage & QC Provenance
        </h4>

        <div style="position:relative; margin-bottom:20px;">
          ${this._renderLineageChain(tube.lineage)}
        </div>

        <div style="display:flex; gap:10px; margin-top:20px;">
          <button id="btn-decrement-volume" class="btn btn-outline btn-sm" style="flex:1;">
            - 10 µL Aliquot Use
          </button>
          <button id="btn-increment-ft" class="btn btn-outline btn-sm" style="flex:1;">
            Log Freeze-Thaw
          </button>
        </div>
      `;

      // Bind button events inside drawer
      const btnDecVol = drawerBody.querySelector('#btn-decrement-volume');
      if (btnDecVol) {
        btnDecVol.addEventListener('click', () => {
          if (tube.volumeUl >= 10) {
            tube.volumeUl -= 10;
            this.displayTubeLineage(tube);
          }
        });
      }

      const btnIncFT = drawerBody.querySelector('#btn-increment-ft');
      if (btnIncFT) {
        btnIncFT.addEventListener('click', () => {
          tube.freezeThawCycles += 1;
          this.displayTubeLineage(tube);
        });
      }
    }

    this.drawer.classList.add('open');
  }

  /**
   * Generates HTML chain items for experimental lineage.
   * @agent eln-frontend-agent
   * @role Lineage DOM Formatter
   * @private
   * @param {Object} lineage - Lineage provenance dictionary
   * @returns {string} HTML string of lineage steps
   */
  _renderLineageChain(lineage) {
    if (!lineage) return '<p style="color:var(--text-muted); font-size:0.8rem;">No lineage metadata available.</p>';

    const steps = [
      { title: 'Originating Campaign', desc: lineage.campaignName || lineage.campaignId },
      { title: 'Notebook Daily Entry', desc: lineage.dailyEntry },
      { title: 'Expression Construct', desc: lineage.constructId },
      { title: 'FPLC Fraction Pool', desc: lineage.fplcPoolId },
      { title: 'QC UV-Vis NanoDrop', desc: lineage.nanoDropId },
      { title: 'SDS-PAGE Gel Verification', desc: lineage.gelLaneId },
      { title: 'Formulation Buffer', desc: lineage.buffer }
    ].filter((s) => s.desc);

    return steps.map((s) => `
      <div class="lineage-chain-item">
        <div class="lineage-dot"></div>
        <div style="font-size:0.8rem; font-weight:700; color:var(--text-primary);">${s.title}</div>
        <div style="font-size:0.8rem; color:var(--text-secondary);">${s.desc}</div>
      </div>
    `).join('');
  }

  /**
   * Sets active box dimensions (9x9 or 10x10).
   * @agent eln-frontend-agent
   * @role Box Topology Switcher
   * @param {string} dimensions - '9x9' or '10x10'
   * @returns {void}
   */
  setDimensions(dimensions) {
    if (dimensions !== '9x9' && dimensions !== '10x10') {
      throw new Error(`Invalid dimensions: ${dimensions}. Expected '9x9' or '10x10'.`);
    }
    this.options.boxDimensions = dimensions;
    this.render();
  }

  /**
   * Inserts or updates a tube in a specified well position.
   * @agent eln-frontend-agent
   * @role Tube Storage Controller
   * @param {string} coord - Well coordinate (e.g. 'C5')
   * @param {LimsTube} tubeData - Tube metadata
   * @returns {void}
   */
  storeTube(coord, tubeData) {
    this.activeBox.tubes.set(coord, tubeData);
    this.render();
  }
}
