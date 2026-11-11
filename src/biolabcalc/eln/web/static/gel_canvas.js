/**
 * @file gel_canvas.js
 * @description Interactive Bio-Rad SDS-PAGE / Agarose Gel Canvas & Molecular Weight Estimator.
 * @architecture Dual-layer HTML5 Canvas + SVG overlay supporting draggable lane boundary guides,
 *               semi-logarithmic ladder calibration curves (log10 MW vs Rf), band detection,
 *               database entity linking pills (Construct, FPLC Pool, NanoDrop ID), and publication export.
 */

/**
 * Represents a single ladder band standard.
 * @typedef {Object} LadderBand
 * @property {number} mw - Molecular weight in kDa
 * @property {number} y - Pixel Y position along the gel
 * @property {number} rf - Relative mobility factor (0.0 to 1.0)
 * @property {string} label - Text label (e.g., '250 kDa')
 * @property {boolean} isReference - Whether this is a prominent reference band (e.g., 50 kDa or 75 kDa)
 */

/**
 * Represents a single gel lane with loaded sample metadata and entity linkages.
 * @typedef {Object} GelLane
 * @property {number} index - 1-based lane number
 * @property {number} x - Center horizontal coordinate in pixels
 * @property {number} width - Lane width in pixels
 * @property {string} sampleName - Sample description (e.g., 'Ni-NTA Elution Pool B4-B8')
 * @property {string} sampleType - Sample type ('ladder', 'lysate', 'purified', 'control')
 * @property {Array<{y: number, mw: number, rf: number, intensity: number}>} bands - Detected bands
 * @property {Object} entities - Linked database entities
 * @property {string} [entities.constructId] - Linked Expression Construct ID
 * @property {string} [entities.fractionPoolId] - Linked FPLC Fraction Pool ID
 * @property {string} [entities.nanoDropId] - Linked NanoDrop Spectrum ID
 */

/**
 * GelCanvasViewer Class: Renders interactive gel canvas and performs Rf/MW calculations.
 * @role Scientific electrophoresis canvas controller
 */
export class GelCanvasViewer {
  /**
   * Initializes the GelCanvasViewer instance.
   * @role Component Constructor
   * @param {string|HTMLCanvasElement} canvasElement - Canvas element or ID
   * @param {Object} options - Configuration options
   * @param {Function} [options.onLaneSelect] - Callback when a lane is selected
   * @param {Function} [options.onBandsUpdated] - Callback when bands or MW estimates change
   */
  constructor(canvasElement, options = {}) {
    this.canvas = typeof canvasElement === 'string' ? document.getElementById(canvasElement) : canvasElement;
    if (!this.canvas) {
      throw new Error(`[GelCanvasViewer] Canvas element not found: ${canvasElement}`);
    }
    this.ctx = this.canvas.getContext('2d');
    this.options = Object.assign({
      dyeFrontY: 420,
      wellTopY: 60,
      ladderLaneIndex: 1,
      onLaneSelect: null,
      onBandsUpdated: null
    }, options);

    // Canvas Dimensions
    this.width = 720;
    this.height = 480;

    // Display Adjustments
    this.brightness = 1.0;
    this.contrast = 1.0;
    this.isInverted = false;
    this.showLaneMarkers = true;
    this.showBandLabels = true;
    this.showEntities = true;

    // Draggable Interaction State
    this.selectedLaneIndex = 8; // Default select Lane 8 (Purified T7 RNAP)
    this.draggingLane = null;
    this.dragStartX = 0;

    // Bio-Rad Precision Plus Protein Unstained Ladder standard (kDa)
    this.standardLadderMWs = [250, 150, 100, 75, 50, 37, 25, 20, 15, 10];
    this.ladderBands = [];
    this.calibrationFit = { slope: -1.85, intercept: 2.45, rSquared: 0.994 };

    // Lanes Collection
    this.lanes = [];

    // Initialize Default 10-Lane Bio-Rad Criterion Gel for T7 RNAP
    this._initDefaultLanes();
    this._fitLadderCalibration();
    this._bindEvents();
    this.resize();
    this.render();
  }

  /**
   * Initializes standard 10-lane experimental layout for T7 RNAP campaign.
   * @role Data Initialization
   * @private
   * @returns {void}
   */
  _initDefaultLanes() {
    const laneCount = 10;
    const startX = 60;
    const laneSpacing = 64;
    const laneWidth = 48;

    const sampleDefinitions = [
      { name: 'Precision Plus Ladder', type: 'ladder', entities: {} },
      { name: 'Pre-induction WCL', type: 'lysate', entities: { constructId: 'pET-28a-T7RNAP' } },
      { name: 'Post-induction 4h IPTG', type: 'lysate', entities: { constructId: 'pET-28a-T7RNAP' } },
      { name: 'Clarified Supernatant', type: 'lysate', entities: { constructId: 'pET-28a-T7RNAP' } },
      { name: 'Insoluble Pellet', type: 'lysate', entities: { constructId: 'pET-28a-T7RNAP' } },
      { name: 'Ni-NTA Flowthrough', type: 'purified', entities: { fractionPoolId: 'FT-01' } },
      { name: 'Ni-NTA Wash (30mM Imid)', type: 'purified', entities: { fractionPoolId: 'WASH-01' } },
      { name: 'Ni-NTA Elution (Pool B4-B8)', type: 'purified', entities: { constructId: 'pET-28a-T7RNAP', fractionPoolId: 'POOL-B4-B8', nanoDropId: 'ND-2026-0881' } },
      { name: 'Dialyzed Final Bulk', type: 'purified', entities: { constructId: 'pET-28a-T7RNAP', nanoDropId: 'ND-2026-0882' } },
      { name: 'Reference T7 RNAP Standard', type: 'control', entities: { constructId: 'REF-STD-99K' } }
    ];

    this.lanes = [];
    for (let i = 0; i < laneCount; i++) {
      const idx = i + 1;
      const def = sampleDefinitions[i];
      const x = startX + i * laneSpacing;

      const lane = {
        index: idx,
        x,
        width: laneWidth,
        sampleName: def.name,
        sampleType: def.type,
        bands: [],
        entities: def.entities
      };

      if (def.type === 'ladder') {
        // Generate ladder bands
        this.ladderBands = [];
        this.standardLadderMWs.forEach((mw) => {
          // Semi-empirical migration position
          // log10(MW) = -1.85 * Rf + 2.45 -> Rf = (2.45 - log10(MW)) / 1.85
          const rf = (2.45 - Math.log10(mw)) / 1.85;
          const y = this.options.wellTopY + rf * (this.options.dyeFrontY - this.options.wellTopY);
          const band = {
            mw,
            y: +y.toFixed(1),
            rf: +rf.toFixed(3),
            label: `${mw} kDa`,
            isReference: mw === 50 || mw === 75 // prominent reference standards
          };
          this.ladderBands.push(band);
          lane.bands.push({ y: band.y, mw: band.mw, rf: band.rf, intensity: band.isReference ? 0.9 : 0.6 });
        });
      } else if (idx === 8 || idx === 9 || idx === 10) {
        // High purity target band ~98.9 kDa T7 RNA Polymerase
        const rfTarget = (2.45 - Math.log10(98.9)) / 1.85;
        const yTarget = this.options.wellTopY + rfTarget * (this.options.dyeFrontY - this.options.wellTopY);
        lane.bands.push({
          y: +yTarget.toFixed(1),
          mw: 98.9,
          rf: +rfTarget.toFixed(3),
          intensity: 0.95
        });
        // Faint minor band in elution
        if (idx === 8) {
          const rfMinor = (2.45 - Math.log10(45.0)) / 1.85;
          const yMinor = this.options.wellTopY + rfMinor * (this.options.dyeFrontY - this.options.wellTopY);
          lane.bands.push({
            y: +yMinor.toFixed(1),
            mw: 45.0,
            rf: +rfMinor.toFixed(3),
            intensity: 0.12
          });
        }
      } else if (idx === 2 || idx === 3 || idx === 4 || idx === 5) {
        // Lysates with diverse host protein smear and target band
        const rfTarget = (2.45 - Math.log10(98.9)) / 1.85;
        const yTarget = this.options.wellTopY + rfTarget * (this.options.dyeFrontY - this.options.wellTopY);
        if (idx !== 2) {
          lane.bands.push({ y: +yTarget.toFixed(1), mw: 98.9, rf: +rfTarget.toFixed(3), intensity: idx === 5 ? 0.3 : 0.85 });
        }
        // Additional background bands
        [150, 70, 42, 35, 28, 18].forEach((bgMW) => {
          const rf = (2.45 - Math.log10(bgMW)) / 1.85;
          const y = this.options.wellTopY + rf * (this.options.dyeFrontY - this.options.wellTopY);
          lane.bands.push({ y: +y.toFixed(1), mw: bgMW, rf: +rf.toFixed(3), intensity: Math.random() * 0.4 + 0.2 });
        });
      }

      this.lanes.push(lane);
    }
  }

  /**
   * Fits semi-log standard curve log10(MW) = a * Rf + b from ladder bands.
   * @role Linear Regression Fitting
   * @private
   * @returns {void}
   */
  _fitLadderCalibration() {
    if (this.ladderBands.length < 2) return;

    let sumX = 0;
    let sumY = 0;
    let sumXY = 0;
    let sumX2 = 0;
    const n = this.ladderBands.length;

    for (const band of this.ladderBands) {
      const x = band.rf;
      const y = Math.log10(band.mw);
      sumX += x;
      sumY += y;
      sumXY += x * y;
      sumX2 += x * x;
    }

    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;

    // Calculate R² (coefficient of determination)
    const meanY = sumY / n;
    let ssTot = 0;
    let ssRes = 0;
    for (const band of this.ladderBands) {
      const yActual = Math.log10(band.mw);
      const yPredicted = slope * band.rf + intercept;
      ssTot += Math.pow(yActual - meanY, 2);
      ssRes += Math.pow(yActual - yPredicted, 2);
    }
    const rSquared = 1 - ssRes / ssTot;

    this.calibrationFit = {
      slope: +slope.toFixed(4),
      intercept: +intercept.toFixed(4),
      rSquared: +rSquared.toFixed(4)
    };
  }

  /**
   * Estimates molecular weight from relative mobility (Rf).
   * @role MW Prediction Engine
   * @param {number} rf - Relative mobility factor (0.0 to 1.0)
   * @returns {number} Estimated molecular weight in kDa
   */
  estimateMWFromRf(rf) {
    const logMW = this.calibrationFit.slope * rf + this.calibrationFit.intercept;
    return +Math.pow(10, logMW).toFixed(1);
  }

  /**
   * Binds interaction listeners for dragging lane guides and selecting entities.
   * @role Event Handling
   * @private
   * @returns {void}
   */
  _bindEvents() {
    this.canvas.addEventListener('mousedown', (e) => this._handleMouseDown(e));
    window.addEventListener('mousemove', (e) => this._handleMouseMove(e));
    window.addEventListener('mouseup', () => this._handleMouseUp());
  }

  /**
   * Resizes canvas buffer for crisp high-DPI displays.
   * @role Display Scaling
   * @returns {void}
   */
  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width || 720;
    this.height = rect.height || 480;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.ctx.scale(dpr, dpr);
  }

  /**
   * Master render method: draws background, Coomassie gel matrix, bands, and overlays.
   * @role Master Render Method
   * @returns {void}
   */
  render() {
    const { ctx, width, height } = this;
    ctx.clearRect(0, 0, width, height);

    // 1. Synthetic Coomassie Gel Matrix Background
    ctx.save();
    ctx.filter = `brightness(${this.brightness}) contrast(${this.contrast}) ${this.isInverted ? 'invert(1)' : ''}`;

    // Deep gel gradient (polyacrylamide slab)
    const gelGrad = ctx.createLinearGradient(0, 0, 0, height);
    gelGrad.addColorStop(0, '#0a1026');
    gelGrad.addColorStop(0.5, '#0d1b3e');
    gelGrad.addColorStop(1, '#050a1a');
    ctx.fillStyle = gelGrad;
    ctx.fillRect(0, 0, width, height);

    // Gel well loading zone line
    ctx.strokeStyle = '#1e3a8a';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(30, this.options.wellTopY);
    ctx.lineTo(width - 30, this.options.wellTopY);
    ctx.stroke();

    // Bromophenol Blue dye front line
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(30, this.options.dyeFrontY);
    ctx.lineTo(width - 30, this.options.dyeFrontY);
    ctx.stroke();
    ctx.setLineDash([]);

    // 2. Render Protein Bands
    for (const lane of this.lanes) {
      this._renderLaneBands(lane);
    }
    ctx.restore();

    // 3. Lane Boundary Markers and Selection Highlights
    if (this.showLaneMarkers) {
      this._renderLaneGuides();
    }

    // 4. Ladder Annotations (left sidebar)
    if (this.showBandLabels) {
      this._renderLadderLabels();
    }

    // 5. Database Entity Linking Pills
    if (this.showEntities) {
      this._renderEntityPills();
    }
  }

  /**
   * Renders bands within a single lane with gaussian blur and intensity gradients.
   * @role Band Visualizer
   * @private
   * @param {GelLane} lane - Target lane
   * @returns {void}
   */
  _renderLaneBands(lane) {
    const { ctx } = this;
    const halfW = lane.width / 2;

    for (const band of lane.bands) {
      const alpha = Math.min(1.0, band.intensity * 0.95);
      const bandHeight = band.intensity > 0.8 ? 9 : 6;

      ctx.save();
      // Band gradient across horizontal lane width
      const grad = ctx.createRadialGradient(
        lane.x, band.y, 2,
        lane.x, band.y, halfW
      );
      grad.addColorStop(0, `rgba(186, 230, 253, ${alpha})`); // Coomassie bright core
      grad.addColorStop(0.4, `rgba(56, 189, 248, ${alpha * 0.8})`);
      grad.addColorStop(1, 'rgba(56, 189, 248, 0)');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.ellipse(lane.x, band.y, halfW - 4, bandHeight / 2, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  }

  /**
   * Renders vertical draggable boundary guides and lane headers.
   * @role Lane Guide Visualizer
   * @private
   * @returns {void}
   */
  _renderLaneGuides() {
    const { ctx, height } = this;

    for (const lane of this.lanes) {
      const isSelected = lane.index === this.selectedLaneIndex;
      const left = lane.x - lane.width / 2;
      const right = lane.x + lane.width / 2;

      // Selection halo
      if (isSelected) {
        ctx.fillStyle = 'rgba(59, 130, 246, 0.15)';
        ctx.fillRect(left, this.options.wellTopY - 20, lane.width, height - this.options.wellTopY);
      }

      // Vertical guide lines
      ctx.strokeStyle = isSelected ? '#3b82f6' : 'rgba(255, 255, 255, 0.12)';
      ctx.lineWidth = isSelected ? 1.5 : 1;
      ctx.beginPath();
      ctx.moveTo(left, this.options.wellTopY - 14);
      ctx.lineTo(left, height - 20);
      ctx.moveTo(right, this.options.wellTopY - 14);
      ctx.lineTo(right, height - 20);
      ctx.stroke();

      // Lane Number Badge at Top
      ctx.fillStyle = isSelected ? '#3b82f6' : '#1e293b';
      ctx.beginPath();
      ctx.roundRect(lane.x - 14, 18, 28, 20, 4);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 10px var(--font-mono, monospace)';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${lane.index}`, lane.x, 28);
    }
  }

  /**
   * Renders ladder molecular weight callouts alongside the ladder lane.
   * @role Ladder Legend Visualizer
   * @private
   * @returns {void}
   */
  _renderLadderLabels() {
    const { ctx } = this;
    const ladderX = 45;

    ctx.font = 'bold 9px var(--font-mono, monospace)';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    for (const band of this.ladderBands) {
      ctx.fillStyle = band.isReference ? '#38bdf8' : '#94a3b8';
      ctx.fillText(band.label, ladderX, band.y);

      // Dash connector line to ladder band
      ctx.strokeStyle = band.isReference ? '#38bdf8' : 'rgba(148, 163, 184, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ladderX + 4, band.y);
      ctx.lineTo(ladderX + 12, band.y);
      ctx.stroke();
    }
  }

  /**
   * Renders entity linking pills below each lane.
   * @role Entity Tagging Visualizer
   * @private
   * @returns {void}
   */
  _renderEntityPills() {
    const { ctx, height } = this;
    const bottomY = height - 26;

    for (const lane of this.lanes) {
      if (lane.entities.fractionPoolId) {
        ctx.fillStyle = '#10b981';
        ctx.beginPath();
        ctx.roundRect(lane.x - 22, bottomY, 44, 16, 4);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 8px var(--font-sans, sans-serif)';
        ctx.textAlign = 'center';
        ctx.fillText('FPLC Pool', lane.x, bottomY + 10);
      }
    }
  }

  /**
   * Handles lane clicking and drag initiation.
   * @role Mouse Event Handler
   * @private
   * @param {MouseEvent} e - Mouse event
   * @returns {void}
   */
  _handleMouseDown(e) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;

    for (const lane of this.lanes) {
      const left = lane.x - lane.width / 2;
      const right = lane.x + lane.width / 2;
      if (x >= left && x <= right) {
        this.selectedLaneIndex = lane.index;
        this.draggingLane = lane;
        this.dragStartX = x;
        if (typeof this.options.onLaneSelect === 'function') {
          this.options.onLaneSelect(lane);
        }
        this.render();
        break;
      }
    }
  }

  /**
   * Handles dragging to adjust lane horizontal position.
   * @role Drag Reposition Handler
   * @private
   * @param {MouseEvent} e - Mouse event
   * @returns {void}
   */
  _handleMouseMove(e) {
    if (!this.draggingLane) return;
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const delta = x - this.dragStartX;

    this.draggingLane.x += delta;
    this.dragStartX = x;
    this.render();
  }

  /**
   * Finalizes lane dragging and recalculates calibrations.
   * @role Drag End Handler
   * @private
   * @returns {void}
   */
  _handleMouseUp() {
    if (this.draggingLane) {
      this.draggingLane = null;
      this._fitLadderCalibration();
      this.render();
    }
  }

  /**
   * Sets contrast and brightness visual parameters.
   * @role Visual Filter Controller
   * @param {number} contrast - Contrast factor (e.g., 0.5 to 2.0)
   * @param {number} brightness - Brightness factor (e.g., 0.5 to 2.0)
   * @returns {void}
   */
  setImageFilters(contrast, brightness) {
    this.contrast = contrast;
    this.brightness = brightness;
    this.render();
  }

  /**
   * Toggles color inversion (white background for publication).
   * @role Display Inversion Toggle
   * @returns {boolean} New inversion state
   */
  toggleInvert() {
    this.isInverted = !this.isInverted;
    this.render();
    return this.isInverted;
  }

  /**
   * Links a database entity to a specific lane.
   * @role Database Entity Linker
   * @param {number} laneIndex - Target 1-based lane number
   * @param {string} entityType - Entity type ('constructId'|'fractionPoolId'|'nanoDropId')
   * @param {string} entityValue - Entity primary key
   * @returns {void}
   */
  linkEntity(laneIndex, entityType, entityValue) {
    const lane = this.lanes.find((l) => l.index === laneIndex);
    if (lane) {
      lane.entities[entityType] = entityValue;
      this.render();
    }
  }

  /**
   * Exports high-resolution annotated publication figure.
   * @role Publication Exporter
   * @returns {string} High-resolution Base64 PNG URL
   */
  exportPublicationFigure() {
    return this.canvas.toDataURL('image/png');
  }
}
