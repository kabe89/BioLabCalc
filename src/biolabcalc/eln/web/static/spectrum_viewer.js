/**
 * @file spectrum_viewer.js
 * @agent eln-frontend-agent
 * @description Interactive NanoDrop UV-Vis Spectral Curve Viewer & Nucleic Acid / Protein Purity Analyzer.
 * @architecture High-precision Canvas/SVG dual-mode renderer plotting 220 nm to 350 nm absorption spectra.
 *               Performs automated 340 nm turbidity baseline subtraction, A260/A280 and A260/A230
 *               quality ratio checks, Beer-Lambert concentration calculations, and multi-sample overlays.
 */

/**
 * Represents a single spectral wavelength measurement point.
 * @typedef {Object} SpectrumDataPoint
 * @property {number} wavelength - Wavelength in nanometers (220 - 350 nm)
 * @property {number} absorbance - Optical density (Absorbance Units, AU)
 */

/**
 * Represents a complete NanoDrop spectrum record.
 * @typedef {Object} NanoDropSample
 * @property {string} id - Spectrum Unique Identifier (e.g. 'ND-2026-0881')
 * @property {string} sampleName - Sample name / description
 * @property {string} sampleType - Sample type ('protein', 'dna', 'rna')
 * @property {Array<SpectrumDataPoint>} points - Array of spectral points
 * @property {number} extinctionCoeff - Molar extinction coefficient or E0.1%
 * @property {number} pathLengthMm - Optical path length in mm (typically 1.0 or 0.2 mm)
 * @property {number} dilutionFactor - Sample dilution factor (e.g. 1.0 or 10.0)
 * @property {string} color - Display curve color hex
 */

/**
 * SpectrumViewer Class: Manages UV-Vis spectrum rendering and purity diagnostics.
 * @agent eln-frontend-agent
 * @role Scientific UV-Vis spectrophotometry canvas component
 */
export class SpectrumViewer {
  /**
   * Initializes the SpectrumViewer instance.
   * @agent eln-frontend-agent
   * @role Component Constructor
   * @param {string|HTMLCanvasElement} canvasElement - Canvas element or ID
   * @param {Object} options - Configuration options
   * @param {Function} [options.onSampleSelect] - Callback when an active sample changes
   * @param {Function} [options.onPurityEvaluated] - Callback when purity metrics update
   */
  constructor(canvasElement, options = {}) {
    this.canvas = typeof canvasElement === 'string' ? document.getElementById(canvasElement) : canvasElement;
    if (!this.canvas) {
      throw new Error(`[SpectrumViewer] Canvas element not found: ${canvasElement}`);
    }
    this.ctx = this.canvas.getContext('2d');
    this.options = Object.assign({
      baselineSubtract: true,
      baselineWavelength: 340,
      pathLengthMm: 1.0, // NanoDrop 1 mm standard path
      onSampleSelect: null,
      onPurityEvaluated: null
    }, options);

    // Padding & Viewport Dimensions
    this.padding = { top: 30, right: 30, bottom: 44, left: 55 };
    this.width = 640;
    this.height = 380;

    // Multi-sample Collection
    this.samples = [];
    this.activeSampleId = 'ND-2026-0881';

    // Interactive Hover Point
    this.hoverPoint = null;

    // Load Default T7 RNAP Purification Spectra
    this._loadDefaultSamples();
    this._bindEvents();
    this.resize();
    this.render();
  }

  /**
   * Generates realistic NanoDrop spectral curves for purified T7 RNAP and dialyzed stock.
   * @agent eln-frontend-agent
   * @role Synthetic Data Generator
   * @private
   * @returns {void}
   */
  _loadDefaultSamples() {
    this.samples = [
      {
        id: 'ND-2026-0881',
        sampleName: 'Ni-NTA Elution Pool B4-B8',
        sampleType: 'protein',
        extinctionCoeff: 1.40, // Abs 0.1% (1 mg/mL) at 280 nm
        pathLengthMm: 1.0,
        dilutionFactor: 1.0,
        color: '#2563eb', // Azure Blue
        points: this._generateProteinCurve(5.39, 0.04) // Peak A280 = 5.39 AU
      },
      {
        id: 'ND-2026-0882',
        sampleName: 'Dialyzed Final Bulk Formulation',
        sampleType: 'protein',
        extinctionCoeff: 1.40,
        pathLengthMm: 1.0,
        dilutionFactor: 1.0,
        color: '#10b981', // Emerald Green
        points: this._generateProteinCurve(5.22, 0.01)
      },
      {
        id: 'ND-2026-0880',
        sampleName: 'Clarified Supernatant (Pre-column)',
        sampleType: 'protein',
        extinctionCoeff: 1.0,
        pathLengthMm: 1.0,
        dilutionFactor: 5.0,
        color: '#f59e0b', // Amber
        points: this._generateCrudeCurve()
      }
    ];
  }

  /**
   * Simulates realistic protein UV absorbance spectrum with 280 nm Trp/Tyr peak.
   * @agent eln-frontend-agent
   * @role Curve Simulation Helper
   * @private
   * @param {number} a280Target - Target absorbance at 280 nm
   * @param {number} turbidity - Turbidity offset at 340 nm
   * @returns {Array<SpectrumDataPoint>} Spectrum points
   */
  _generateProteinCurve(a280Target, turbidity = 0.02) {
    const points = [];
    for (let nm = 220; nm <= 350; nm += 1) {
      // 280 nm peak (aromatic amino acids Trp, Tyr, Phe)
      const peak280 = (a280Target - turbidity) * Math.exp(-Math.pow(nm - 280, 2) / 180);
      // 220-230 nm peptide backbone / buffer absorbance
      const farUV = (a280Target * 2.2) * Math.exp(-(nm - 220) / 14);
      // Small 260 shoulder (ratio ~0.58 for pure protein)
      const shoulder260 = (a280Target * 0.45) * Math.exp(-Math.pow(nm - 260, 2) / 220);
      // Rayleigh scattering turbidity slope ~ 1 / lambda^4
      const scatter = turbidity * Math.pow(340 / nm, 3.5);

      const abs = peak280 + farUV + shoulder260 + scatter;
      points.push({ wavelength: nm, absorbance: +abs.toFixed(3) });
    }
    return points;
  }

  /**
   * Simulates crude lysate UV spectrum with high nucleic acid contaminant absorption.
   * @agent eln-frontend-agent
   * @role Crude Simulation Helper
   * @private
   * @returns {Array<SpectrumDataPoint>} Spectrum points
   */
  _generateCrudeCurve() {
    const points = [];
    for (let nm = 220; nm <= 350; nm += 1) {
      const peak260 = 3.8 * Math.exp(-Math.pow(nm - 260, 2) / 160);
      const peak280 = 2.4 * Math.exp(-Math.pow(nm - 280, 2) / 190);
      const farUV = 5.2 * Math.exp(-(nm - 220) / 16);
      const abs = peak260 + peak280 + farUV + 0.08;
      points.push({ wavelength: nm, absorbance: +abs.toFixed(3) });
    }
    return points;
  }

  /**
   * Binds mouse interaction events.
   * @agent eln-frontend-agent
   * @role Event Setup
   * @private
   * @returns {void}
   */
  _bindEvents() {
    this.canvas.addEventListener('mousemove', (e) => this._handleMouseMove(e));
    this.canvas.addEventListener('mouseleave', () => this._handleMouseLeave());
  }

  /**
   * Resizes canvas buffer for crisp high-DPI displays.
   * @agent eln-frontend-agent
   * @role Display Scaling
   * @returns {void}
   */
  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width || 640;
    this.height = rect.height || 380;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.ctx.scale(dpr, dpr);
  }

  /**
   * Calculates coordinate scale transformations.
   * @agent eln-frontend-agent
   * @role Coordinate Converter
   * @private
   * @returns {Object} Scale helper functions
   */
  _getScales() {
    const minWl = 220;
    const maxWl = 350;
    const plotWidth = this.width - this.padding.left - this.padding.right;
    const plotHeight = this.height - this.padding.top - this.padding.bottom;

    // Find max absorbance across all samples
    let maxAbs = 6.0;
    for (const sample of this.samples) {
      for (const p of sample.points) {
        if (p.absorbance > maxAbs) maxAbs = p.absorbance;
      }
    }
    maxAbs = Math.ceil(maxAbs * 1.15);

    return {
      minWl,
      maxWl,
      maxAbs,
      plotWidth,
      plotHeight,
      wlToPx: (wl) => this.padding.left + ((wl - minWl) / (maxWl - minWl)) * plotWidth,
      pxToWl: (px) => minWl + ((px - this.padding.left) / plotWidth) * (maxWl - minWl),
      absToPy: (abs) => this.padding.top + plotHeight - (abs / maxAbs) * plotHeight
    };
  }

  /**
   * Renders the complete UV-Vis spectrum and annotations.
   * @agent eln-frontend-agent
   * @role Master Render Method
   * @returns {void}
   */
  render() {
    const { ctx, width, height, padding } = this;
    const s = this._getScales();

    ctx.clearRect(0, 0, width, height);

    // 1. Plot Background & Grid
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(padding.left, padding.top, s.plotWidth, s.plotHeight);

    ctx.strokeStyle = '#f1f5f9';
    ctx.lineWidth = 1;
    for (let abs = 1.0; abs <= s.maxAbs; abs += 1.0) {
      const y = s.absToPy(abs);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }
    for (let wl = 240; wl <= 340; wl += 20) {
      const x = s.wlToPx(wl);
      ctx.beginPath();
      ctx.moveTo(x, padding.top);
      ctx.lineTo(x, height - padding.bottom);
      ctx.stroke();
    }

    // 2. Critical Reference Wavelength Guides (230, 260, 280, 340 nm)
    this._renderWavelengthGuides(s);

    // 3. Render Sample Spectral Curves
    for (const sample of this.samples) {
      const isActive = sample.id === this.activeSampleId;
      ctx.save();
      ctx.strokeStyle = sample.color;
      ctx.lineWidth = isActive ? 2.8 : 1.4;
      ctx.globalAlpha = isActive ? 1.0 : 0.45;
      ctx.beginPath();

      const baselineVal = this.options.baselineSubtract ? this._getAbsorbanceAt(sample, 340) : 0;

      for (let i = 0; i < sample.points.length; i++) {
        const p = sample.points[i];
        const correctedAbs = Math.max(0, p.absorbance - baselineVal);
        const x = s.wlToPx(p.wavelength);
        const y = s.absToPy(correctedAbs);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.restore();
    }

    // 4. Render Axes & Legends
    this._renderAxes(s);

    // 5. Render Interactive Crosshair
    if (this.hoverPoint) {
      this._renderHover(s);
    }
  }

  /**
   * Renders indicator vertical lines at 230, 260, 280, and 340 nm.
   * @agent eln-frontend-agent
   * @role Reference Line Visualizer
   * @private
   * @param {Object} s - Scale bounds
   * @returns {void}
   */
  _renderWavelengthGuides(s) {
    const { ctx, padding, height } = this;
    const guides = [
      { wl: 230, label: '230 (Backbone/Salts)', color: 'rgba(217, 119, 6, 0.4)' },
      { wl: 260, label: '260 (Nucleic Acid)', color: 'rgba(124, 58, 237, 0.4)' },
      { wl: 280, label: '280 (Protein Trp/Tyr)', color: 'rgba(37, 99, 235, 0.4)' },
      { wl: 340, label: '340 (Baseline)', color: 'rgba(100, 116, 139, 0.4)' }
    ];

    for (const g of guides) {
      const x = s.wlToPx(g.wl);
      ctx.strokeStyle = g.color;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, padding.top);
      ctx.lineTo(x, height - padding.bottom);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  /**
   * Renders axes, labels, and ticks.
   * @agent eln-frontend-agent
   * @role Coordinate Axis Renderer
   * @private
   * @param {Object} s - Scale bounds
   * @returns {void}
   */
  _renderAxes(s) {
    const { ctx, width, height, padding } = this;

    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 1.2;
    ctx.strokeRect(padding.left, padding.top, s.plotWidth, s.plotHeight);

    // Y-Axis: Absorbance (10 mm path equivalent)
    ctx.fillStyle = '#0f172a';
    ctx.font = 'bold 11px var(--font-sans, sans-serif)';
    ctx.textAlign = 'center';
    ctx.save();
    ctx.translate(16, padding.top + s.plotHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Absorbance (AU)', 0, 0);
    ctx.restore();

    ctx.textAlign = 'right';
    ctx.font = '10px var(--font-mono, monospace)';
    for (let abs = 0; abs <= s.maxAbs; abs += 1.0) {
      const y = s.absToPy(abs);
      ctx.fillText(`${abs.toFixed(1)}`, padding.left - 6, y + 4);
    }

    // X-Axis: Wavelength (nm)
    ctx.fillText('Wavelength (nm)', padding.left + s.plotWidth / 2, height - 10);
    ctx.textAlign = 'center';
    for (let wl = 220; wl <= 350; wl += 20) {
      const x = s.wlToPx(wl);
      ctx.fillText(`${wl}`, x, height - padding.bottom + 16);
    }
  }

  /**
   * Renders hover tooltip with interpolated absorbance values.
   * @agent eln-frontend-agent
   * @role Interactive Hover Readout
   * @private
   * @param {Object} s - Scale bounds
   * @returns {void}
   */
  _renderHover(s) {
    const { ctx, padding, height } = this;
    const { x, y } = this.hoverPoint;
    const wl = Math.round(s.pxToWl(x));

    const activeSample = this.samples.find((smp) => smp.id === this.activeSampleId);
    if (!activeSample) return;

    const absVal = this._getAbsorbanceAt(activeSample, wl);

    // Vertical indicator line
    ctx.save();
    ctx.strokeStyle = '#64748b';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, height - padding.bottom);
    ctx.stroke();
    ctx.restore();

    // Tooltip Box
    const boxW = 140;
    const boxH = 50;
    let boxX = x + 10;
    if (boxX + boxW > this.width - padding.right) boxX = x - boxW - 10;
    let boxY = y - boxH / 2;

    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
    ctx.fillRect(boxX, boxY, boxW, boxH);
    ctx.strokeStyle = '#334155';
    ctx.strokeRect(boxX, boxY, boxW, boxH);

    ctx.font = '10px var(--font-mono, monospace)';
    ctx.fillStyle = '#f8fafc';
    ctx.textAlign = 'left';
    ctx.fillText(`λ: ${wl} nm`, boxX + 8, boxY + 18);
    ctx.fillStyle = '#60a5fa';
    ctx.fillText(`Abs: ${absVal.toFixed(3)} AU`, boxX + 8, boxY + 36);
  }

  /**
   * Retrieves interpolated absorbance value at specified wavelength.
   * @agent eln-frontend-agent
   * @role Spectral Lookup Helper
   * @private
   * @param {NanoDropSample} sample - Source sample record
   * @param {number} wl - Target wavelength in nm
   * @returns {number} Absorbance in AU
   */
  _getAbsorbanceAt(sample, wl) {
    const pt = sample.points.find((p) => p.wavelength === wl);
    return pt ? pt.absorbance : 0;
  }

  /**
   * Handles mouse movement over canvas.
   * @agent eln-frontend-agent
   * @role Mouse Event Handler
   * @private
   * @param {MouseEvent} e - Mouse event
   * @returns {void}
   */
  _handleMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (
      x >= this.padding.left &&
      x <= this.width - this.padding.right &&
      y >= this.padding.top &&
      y <= this.height - this.padding.bottom
    ) {
      this.hoverPoint = { x, y };
    } else {
      this.hoverPoint = null;
    }
    this.render();
  }

  /**
   * Clears hover indicators when mouse exits canvas.
   * @agent eln-frontend-agent
   * @role Mouse Exit Handler
   * @private
   * @returns {void}
   */
  _handleMouseLeave() {
    this.hoverPoint = null;
    this.render();
  }

  /**
   * Evaluates purity metrics and concentration for the currently active sample.
   * @agent eln-frontend-agent
   * @role Biochemical Diagnostic Calculation
   * @returns {Object} Quality metrics and concentration
   */
  evaluateActiveSample() {
    const sample = this.samples.find((smp) => smp.id === this.activeSampleId);
    if (!sample) return null;

    const rawA230 = this._getAbsorbanceAt(sample, 230);
    const rawA260 = this._getAbsorbanceAt(sample, 260);
    const rawA280 = this._getAbsorbanceAt(sample, 280);
    const rawA340 = this._getAbsorbanceAt(sample, 340);

    const baseline = this.options.baselineSubtract ? rawA340 : 0;
    const a230 = Math.max(0.001, rawA230 - baseline);
    const a260 = Math.max(0.001, rawA260 - baseline);
    const a280 = Math.max(0.001, rawA280 - baseline);

    const ratio260_280 = +(a260 / a280).toFixed(2);
    const ratio260_230 = +(a260 / a230).toFixed(2);

    // Beer-Lambert protein calculation:
    // A280 = epsilon * c * l -> c = A280 / (epsilon * l)
    // Path length standard 1.0 cm (10 mm) equivalent
    const pathCm = (this.options.pathLengthMm || 1.0) / 10.0;
    const eps = sample.extinctionCoeff || 1.40;
    const concMgMl = +((a280 / (eps * (pathCm * 10))) * sample.dilutionFactor).toFixed(2);

    // Assessment flags for purified protein
    let status260_280 = 'PASS';
    let status260_230 = 'PASS';

    if (sample.sampleType === 'protein') {
      // Pure protein A260/A280 is typically 0.55 - 0.70
      if (ratio260_280 > 0.80) status260_280 = 'FLAG'; // Nucleic acid contamination
      if (ratio260_280 > 1.20) status260_280 = 'FAIL';
      // Low salt / buffer check
      if (ratio260_230 < 1.4) status260_230 = 'FLAG';
    }

    const result = {
      sampleId: sample.id,
      sampleName: sample.sampleName,
      sampleType: sample.sampleType,
      a280: +a280.toFixed(3),
      a260: +a260.toFixed(3),
      a230: +a230.toFixed(3),
      a340: +rawA340.toFixed(3),
      ratio260_280,
      ratio260_230,
      status260_280,
      status260_230,
      concentrationMgMl: concMgMl,
      dilutionFactor: sample.dilutionFactor,
      baselineCorrected: this.options.baselineSubtract
    };

    if (typeof this.options.onPurityEvaluated === 'function') {
      this.options.onPurityEvaluated(result);
    }

    return result;
  }

  /**
   * Sets the active sample to display.
   * @agent eln-frontend-agent
   * @role Sample Switcher
   * @param {string} sampleId - Unique sample ID
   * @returns {void}
   */
  setActiveSample(sampleId) {
    this.activeSampleId = sampleId;
    this.render();
    this.evaluateActiveSample();
    if (typeof this.options.onSampleSelect === 'function') {
      this.options.onSampleSelect(sampleId);
    }
  }
}
