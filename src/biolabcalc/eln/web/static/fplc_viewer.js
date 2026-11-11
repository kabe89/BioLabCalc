/**
 * @file fplc_viewer.js
 * @description Interactive Multi-Channel FPLC Chromatogram Viewer and Fraction Pooling Engine.
 * @architecture High-performance Canvas/SVG dual-layer renderer supporting UV280 (mAU),
 *               Conductivity (mS/cm), and %B gradient elution channels against Volume (mL) or Time (min).
 *               Features peak integration, fraction marker track (A1-A12, B1-B12), drag selection,
 *               and reactive fraction pooling linking to Gel and LIMS modules.
 */

/**
 * Represents a single collected fraction along the chromatogram.
 * @typedef {Object} FPLCFraction
 * @property {string} id - Fraction identifier (e.g., 'B4')
 * @property {number} startVol - Start volume in mL
 * @property {number} endVol - End volume in mL
 * @property {number} volume - Total fraction volume in mL
 * @property {number} avgUV280 - Average UV280 absorbance across fraction
 * @property {number} estimatedPurity - Estimated purity percentage
 */

/**
 * Represents an integrated chromatographic peak.
 * @typedef {Object} IntegratedPeak
 * @property {number} id - Peak index
 * @property {string} name - Peak label (e.g., 'T7 RNAP Elution Peak')
 * @property {number} startVol - Start volume in mL
 * @property {number} apexVol - Retention volume at peak apex in mL
 * @property {number} endVol - End volume in mL
 * @property {number} apexHeight - Max UV280 height in mAU
 * @property {number} area - Integrated area in mAU·mL
 * @property {number} symmetry - Peak symmetry factor
 * @property {number} resolution - Peak resolution factor
 */

/**
 * FPLCViewer Class: Manages interactive rendering, peak calculation, and fraction pooling.
 * @role Scientific interactive chromatogram canvas component
 */
export class FPLCViewer {
  /**
   * Initializes the FPLCViewer instance.
   * @role Component Constructor
   * @param {string|HTMLCanvasElement} canvasElement - Canvas element or its ID selector
   * @param {Object} options - Configuration options
   * @param {Function} [options.onPoolSelected] - Callback triggered when fractions are pooled
   * @param {Function} [options.onSelectionChange] - Callback triggered on fraction range change
   */
  constructor(canvasElement, options = {}) {
    this.canvas = typeof canvasElement === 'string' ? document.getElementById(canvasElement) : canvasElement;
    if (!this.canvas) {
      throw new Error(`[FPLCViewer] Canvas element not found: ${canvasElement}`);
    }
    this.ctx = this.canvas.getContext('2d');
    this.options = Object.assign({
      extinctionCoefficient: 1.40, // Abs 0.1% (1 mg/mL) at 280 nm for T7 RNAP ~140,000 M-1 cm-1 / MW ~99kDa -> 1.40 mL/(mg*cm)
      pathLengthCm: 0.2, // ÄKTA 2 mm flow cell
      flowRateMlMin: 1.0,
      onPoolSelected: null,
      onSelectionChange: null
    }, options);

    // Padding & Viewport Dimensions
    this.padding = { top: 44, right: 80, bottom: 50, left: 65 };
    
    // Multi-channel Datasets
    this.data = {
      volumes: [],
      uv280: [],        // Blue channel (mAU)
      conductivity: [], // Red channel (mS/cm)
      percentB: []      // Green channel (%)
    };

    // Fractions metadata
    this.fractions = [];
    this.selectedFractionIds = new Set();
    this.isDragging = false;
    this.dragStartFraction = null;

    // Peak integration regions
    this.peaks = [];
    this.showBaseline = true;
    this.showFractions = true;
    this.showPeaks = true;

    // Interactive Hover & Crosshair
    this.hoverPoint = null;

    // Generate Default Synthetic High-Resolution ÄKTA Run (T7 RNAP His6 Ni-NTA)
    this._generateDefaultData();
    this._bindEvents();
    this.resize();
    this.render();
  }

  /**
   * Generates realistic ÄKTA Avant Ni-NTA purification data for T7 RNA Polymerase.
   * @role Internal Synthetic Data Generator
   * @private
   * @returns {void}
   */
  _generateDefaultData() {
    const totalVolume = 48.0; // 48 mL run
    const step = 0.1; // 100 µL sampling
    const count = Math.floor(totalVolume / step);

    this.data.volumes = [];
    this.data.uv280 = [];
    this.data.conductivity = [];
    this.data.percentB = [];

    // Fraction layout: A1-A12 (0 to 24 mL), B1-B12 (24 to 48 mL), 2 mL each fraction
    this.fractions = [];
    let fracIndex = 0;
    const rackLetters = ['A', 'B'];

    for (const letter of rackLetters) {
      for (let num = 1; num <= 12; num++) {
        const id = `${letter}${num}`;
        const start = fracIndex * 2.0;
        const end = (fracIndex + 1) * 2.0;
        this.fractions.push({
          id,
          startVol: start,
          endVol: end,
          volume: 2.0,
          avgUV280: 0,
          estimatedPurity: 0
        });
        fracIndex++;
      }
    }

    // Synthetic profile curves:
    // Flowthrough peak: 3-8 mL (contaminants)
    // Wash peak: 12-16 mL (non-specific binders)
    // Main target peak: 28-36 mL (T7 RNAP eluted with 250 mM Imidazole gradient)
    for (let i = 0; i <= count; i++) {
      const v = +(i * step).toFixed(2);
      this.data.volumes.push(v);

      // %B gradient: 0% up to 20 mL, linear 0%->100% from 20 mL to 40 mL, 100% after
      let b = 0;
      if (v < 20.0) {
        b = 0;
      } else if (v <= 40.0) {
        b = ((v - 20.0) / 20.0) * 100;
      } else {
        b = 100;
      }
      this.data.percentB.push(+b.toFixed(1));

      // Conductivity: follows %B with buffer baseline (approx 15 mS/cm baseline -> 55 mS/cm high salt)
      const cond = 15.0 + (b / 100) * 40.0 + (Math.sin(v * 0.5) * 0.3);
      this.data.conductivity.push(+cond.toFixed(2));

      // Baseline noise
      const baseline = 18.0 + Math.random() * 2.5;

      // Peak 1: Flowthrough (unbound proteins) ~5 mL
      const peak1 = 180.0 * Math.exp(-Math.pow(v - 5.2, 2) / 3.5);
      // Peak 2: Wash peak (weak binders) ~14 mL
      const peak2 = 65.0 * Math.exp(-Math.pow(v - 14.5, 2) / 2.0);
      // Peak 3: Desired Target T7 RNA Polymerase apex ~32.4 mL (Fractions B4-B8)
      const peak3 = 1450.0 * Math.exp(-Math.pow(v - 32.4, 2) / 4.8);
      // Small trailing shoulder ~36 mL
      const shoulder = 110.0 * Math.exp(-Math.pow(v - 36.2, 2) / 3.0);

      const uv = baseline + peak1 + peak2 + peak3 + shoulder;
      this.data.uv280.push(+uv.toFixed(2));
    }

    // Compute average UV for each fraction
    for (const frac of this.fractions) {
      let sumUV = 0;
      let countUV = 0;
      for (let i = 0; i < this.data.volumes.length; i++) {
        const v = this.data.volumes[i];
        if (v >= frac.startVol && v < frac.endVol) {
          sumUV += this.data.uv280[i];
          countUV++;
        }
      }
      frac.avgUV280 = countUV > 0 ? +(sumUV / countUV).toFixed(1) : 0;
      // High purity if within main target elution
      if (frac.startVol >= 28 && frac.endVol <= 38) {
        frac.estimatedPurity = +(95.0 + Math.random() * 4).toFixed(1);
      } else {
        frac.estimatedPurity = +(15.0 + Math.random() * 25).toFixed(1);
      }
    }

    // Pre-populate target peak integration
    this.peaks = [
      {
        id: 1,
        name: 'Flowthrough',
        startVol: 3.5,
        apexVol: 5.2,
        endVol: 8.0,
        apexHeight: 180.5,
        area: 485.2,
        symmetry: 1.12,
        resolution: 1.8
      },
      {
        id: 2,
        name: 'Wash (30mM Imidazole)',
        startVol: 13.0,
        apexVol: 14.5,
        endVol: 16.5,
        apexHeight: 65.2,
        area: 142.0,
        symmetry: 1.05,
        resolution: 2.4
      },
      {
        id: 3,
        name: 'T7 RNAP Elution Peak (His6)',
        startVol: 28.0,
        apexVol: 32.4,
        endVol: 38.0,
        apexHeight: 1468.4,
        area: 4620.8,
        symmetry: 1.02,
        resolution: 4.8
      }
    ];

    // Default selection: Target Fractions B4 to B8 (28.0 to 38.0 mL)
    this.selectedFractionIds = new Set(['B4', 'B5', 'B6', 'B7', 'B8']);
  }

  /**
   * Binds mouse and resize interaction events.
   * @role Event Listener Setup
   * @private
   * @returns {void}
   */
  _bindEvents() {
    window.addEventListener('resize', () => {
      this.resize();
      this.render();
    });

    this.canvas.addEventListener('mousemove', (e) => this._handleMouseMove(e));
    this.canvas.addEventListener('mouseleave', () => this._handleMouseLeave());
    this.canvas.addEventListener('mousedown', (e) => this._handleMouseDown(e));
    window.addEventListener('mouseup', () => this._handleMouseUp());
  }

  /**
   * Adjusts canvas pixel buffer for crisp high-DPI retina rendering.
   * @role Display Resolution Management
   * @returns {void}
   */
  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width || 800;
    this.height = rect.height || 460;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.ctx.scale(dpr, dpr);
  }

  /**
   * Computes min/max scales for multi-axis plotting.
   * @role Coordinate Transform Helper
   * @private
   * @returns {Object} Scale bounds
   */
  _getScales() {
    const maxVol = this.data.volumes[this.data.volumes.length - 1] || 50;
    const maxUV = Math.max(1600, ...this.data.uv280);
    const maxCond = 60; // mS/cm
    const maxPercentB = 100; // %

    const plotWidth = this.width - this.padding.left - this.padding.right;
    const plotHeight = this.height - this.padding.top - this.padding.bottom;

    return {
      minVol: 0,
      maxVol,
      minUV: 0,
      maxUV,
      maxCond,
      maxPercentB,
      plotWidth,
      plotHeight,
      xToPx: (v) => this.padding.left + (v / maxVol) * plotWidth,
      pxToX: (px) => ((px - this.padding.left) / plotWidth) * maxVol,
      uvToPy: (uv) => this.padding.top + plotHeight - (uv / maxUV) * plotHeight,
      condToPy: (c) => this.padding.top + plotHeight - (c / maxCond) * plotHeight,
      bToPy: (b) => this.padding.top + plotHeight - (b / maxPercentB) * plotHeight
    };
  }

  /**
   * Renders the complete multi-channel chromatogram.
   * @role Master Render Method
   * @returns {void}
   */
  render() {
    const { ctx, width, height, padding } = this;
    const s = this._getScales();

    ctx.clearRect(0, 0, width, height);

    // 1. Plot Background Grid
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(padding.left, padding.top, s.plotWidth, s.plotHeight);

    ctx.strokeStyle = '#f1f5f9';
    ctx.lineWidth = 1;
    // Horizontal grid lines (UV280)
    for (let uv = 200; uv <= s.maxUV; uv += 200) {
      const y = s.uvToPy(uv);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }
    // Vertical grid lines (Volume mL)
    for (let v = 5; v <= s.maxVol; v += 5) {
      const x = s.xToPx(v);
      ctx.beginPath();
      ctx.moveTo(x, padding.top);
      ctx.lineTo(x, height - padding.bottom);
      ctx.stroke();
    }

    // 2. Render Integrated Peak Shading
    if (this.showPeaks) {
      this._renderPeakShading(s);
    }

    // 3. Render Fraction Track & Highlights
    if (this.showFractions) {
      this._renderFractions(s);
    }

    // 4. Render Channel Curves
    // Conductivity Channel (Dashed Red)
    ctx.save();
    ctx.beginPath();
    ctx.strokeStyle = '#dc2626';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    for (let i = 0; i < this.data.volumes.length; i++) {
      const x = s.xToPx(this.data.volumes[i]);
      const y = s.condToPy(this.data.conductivity[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();

    // %B Elution Gradient Channel (Solid Green)
    ctx.save();
    ctx.beginPath();
    ctx.strokeStyle = '#059669';
    ctx.lineWidth = 2;
    for (let i = 0; i < this.data.volumes.length; i++) {
      const x = s.xToPx(this.data.volumes[i]);
      const y = s.bToPy(this.data.percentB[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();

    // UV280 Primary Channel (Solid Blue)
    ctx.save();
    ctx.beginPath();
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 2.5;
    for (let i = 0; i < this.data.volumes.length; i++) {
      const x = s.xToPx(this.data.volumes[i]);
      const y = s.uvToPy(this.data.uv280[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();

    // 5. Axes & Labels
    this._renderAxes(s);

    // 6. Interactive Crosshair Hover Readout
    if (this.hoverPoint) {
      this._renderHover(s);
    }
  }

  /**
   * Renders fraction markers and selected fraction fills.
   * @role Fraction Visualizer Sub-system
   * @private
   * @param {Object} s - Scale bounds
   * @returns {void}
   */
  _renderFractions(s) {
    const { ctx, padding, height } = this;
    const trackY = 16;
    const trackH = 22;

    for (const frac of this.fractions) {
      const x1 = s.xToPx(frac.startVol);
      const x2 = s.xToPx(frac.endVol);
      const w = x2 - x1;
      const isSelected = this.selectedFractionIds.has(frac.id);

      // Fraction body fill along top track
      ctx.fillStyle = isSelected ? '#3b82f6' : '#e2e8f0';
      ctx.fillRect(x1 + 1, trackY, w - 2, trackH);

      // Fraction label text
      ctx.fillStyle = isSelected ? '#ffffff' : '#475569';
      ctx.font = 'bold 9px var(--font-mono, monospace)';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(frac.id, x1 + w / 2, trackY + trackH / 2);

      // Vertical column shading across chart if selected
      if (isSelected) {
        ctx.fillStyle = 'rgba(59, 130, 246, 0.12)';
        ctx.fillRect(x1, padding.top, w, s.plotHeight);
        ctx.strokeStyle = 'rgba(59, 130, 246, 0.35)';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.strokeRect(x1, padding.top, w, s.plotHeight);
        ctx.setLineDash([]);
      }

      // Vertical separator ticks
      ctx.strokeStyle = '#cbd5e1';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x1, trackY);
      ctx.lineTo(x1, trackY + trackH + 4);
      ctx.stroke();
    }
  }

  /**
   * Renders peak integration fill and apex labels.
   * @role Peak Integration Renderer
   * @private
   * @param {Object} s - Scale bounds
   * @returns {void}
   */
  _renderPeakShading(s) {
    const { ctx } = this;
    for (const peak of this.peaks) {
      const xStart = s.xToPx(peak.startVol);
      const xEnd = s.xToPx(peak.endVol);

      // Find points in range
      ctx.save();
      ctx.beginPath();
      let first = true;
      for (let i = 0; i < this.data.volumes.length; i++) {
        const v = this.data.volumes[i];
        if (v >= peak.startVol && v <= peak.endVol) {
          const x = s.xToPx(v);
          const y = s.uvToPy(this.data.uv280[i]);
          if (first) {
            ctx.moveTo(x, s.uvToPy(0));
            ctx.lineTo(x, y);
            first = false;
          } else {
            ctx.lineTo(x, y);
          }
        }
      }
      ctx.lineTo(xEnd, s.uvToPy(0));
      ctx.closePath();
      ctx.fillStyle = 'rgba(37, 99, 235, 0.18)';
      ctx.fill();
      ctx.restore();

      // Peak Apex Flag
      const apexX = s.xToPx(peak.apexVol);
      const apexY = s.uvToPy(peak.apexHeight);
      ctx.fillStyle = '#1e3a8a';
      ctx.font = 'bold 10px var(--font-sans, sans-serif)';
      ctx.textAlign = 'center';
      ctx.fillText(`Peak ${peak.id}: ${peak.apexVol} mL`, apexX, apexY - 10);
      ctx.font = '9px var(--font-mono, monospace)';
      ctx.fillStyle = '#64748b';
      ctx.fillText(`${peak.apexHeight} mAU`, apexX, apexY - 22);
    }
  }

  /**
   * Renders chart axes, tick marks, and axis titles.
   * @role Coordinate Axis Renderer
   * @private
   * @param {Object} s - Scale bounds
   * @returns {void}
   */
  _renderAxes(s) {
    const { ctx, width, height, padding } = this;

    ctx.strokeStyle = '#94a3b8';
    ctx.lineWidth = 1.2;

    // Outer chart border
    ctx.strokeRect(padding.left, padding.top, s.plotWidth, s.plotHeight);

    // Left Axis: UV 280 nm (mAU) - Blue
    ctx.fillStyle = '#2563eb';
    ctx.font = 'bold 11px var(--font-sans, sans-serif)';
    ctx.textAlign = 'center';
    ctx.save();
    ctx.translate(16, padding.top + s.plotHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('UV 280 nm (mAU)', 0, 0);
    ctx.restore();

    ctx.textAlign = 'right';
    ctx.font = '10px var(--font-mono, monospace)';
    for (let uv = 0; uv <= s.maxUV; uv += 400) {
      const y = s.uvToPy(uv);
      ctx.fillText(`${uv}`, padding.left - 8, y + 4);
    }

    // Right Axis 1: Conductivity (mS/cm) - Red
    ctx.fillStyle = '#dc2626';
    ctx.font = 'bold 11px var(--font-sans, sans-serif)';
    ctx.save();
    ctx.translate(width - 45, padding.top + s.plotHeight / 2);
    ctx.rotate(Math.PI / 2);
    ctx.fillText('Cond (mS/cm)', 0, 0);
    ctx.restore();

    ctx.textAlign = 'left';
    ctx.font = '10px var(--font-mono, monospace)';
    for (let c = 0; c <= s.maxCond; c += 15) {
      const y = s.condToPy(c);
      ctx.fillText(`${c}`, width - padding.right + 6, y + 4);
    }

    // Right Axis 2: %B Elution Gradient - Green
    ctx.fillStyle = '#059669';
    ctx.font = '10px var(--font-mono, monospace)';
    ctx.textAlign = 'left';
    for (let b = 0; b <= 100; b += 25) {
      const y = s.bToPy(b);
      ctx.fillText(`${b}%`, width - 36, y + 4);
    }

    // Bottom Axis: Volume (mL)
    ctx.fillStyle = '#0f172a';
    ctx.font = 'bold 11px var(--font-sans, sans-serif)';
    ctx.textAlign = 'center';
    ctx.fillText('Elution Volume (mL)', padding.left + s.plotWidth / 2, height - 12);

    ctx.font = '10px var(--font-mono, monospace)';
    for (let v = 0; v <= s.maxVol; v += 5) {
      const x = s.xToPx(v);
      ctx.fillText(`${v}`, x, height - padding.bottom + 16);
    }
  }

  /**
   * Renders hover crosshair and value readout tooltip.
   * @role Interactive Hover Sub-system
   * @private
   * @param {Object} s - Scale bounds
   * @returns {void}
   */
  _renderHover(s) {
    const { ctx, padding, height } = this;
    const { x, y } = this.hoverPoint;
    const vol = s.pxToX(x);

    // Crosshair lines
    ctx.save();
    ctx.strokeStyle = '#64748b';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);

    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, height - padding.bottom);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(this.width - padding.right, y);
    ctx.stroke();
    ctx.restore();

    // Closest data interpolation
    const idx = Math.min(
      this.data.volumes.length - 1,
      Math.max(0, Math.round((vol / s.maxVol) * (this.data.volumes.length - 1)))
    );
    const uvVal = this.data.uv280[idx];
    const condVal = this.data.conductivity[idx];
    const bVal = this.data.percentB[idx];

    // Readout Box
    const boxW = 160;
    const boxH = 76;
    let boxX = x + 12;
    if (boxX + boxW > this.width - padding.right) boxX = x - boxW - 12;
    let boxY = y - boxH / 2;
    if (boxY < padding.top) boxY = padding.top + 6;
    if (boxY + boxH > height - padding.bottom) boxY = height - padding.bottom - boxH - 6;

    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1;
    ctx.fillRect(boxX, boxY, boxW, boxH);
    ctx.strokeRect(boxX, boxY, boxW, boxH);

    ctx.font = '10px var(--font-mono, monospace)';
    ctx.fillStyle = '#f8fafc';
    ctx.textAlign = 'left';
    ctx.fillText(`Vol: ${vol.toFixed(2)} mL`, boxX + 8, boxY + 16);
    ctx.fillStyle = '#60a5fa';
    ctx.fillText(`UV280: ${uvVal.toFixed(1)} mAU`, boxX + 8, boxY + 32);
    ctx.fillStyle = '#f87171';
    ctx.fillText(`Cond:  ${condVal.toFixed(1)} mS/cm`, boxX + 8, boxY + 48);
    ctx.fillStyle = '#34d399';
    ctx.fillText(`%B:    ${bVal.toFixed(1)} %`, boxX + 8, boxY + 64);
  }

  /**
   * Handles mouse movement for hover readouts and drag-box selection.
   * @role Mouse Event Handler
   * @private
   * @param {MouseEvent} e - Mouse event
   * @returns {void}
   */
  _handleMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const s = this._getScales();

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

    // Dragging fraction range
    if (this.isDragging && this.dragStartFraction) {
      const currentVol = s.pxToX(x);
      const targetFrac = this.fractions.find((f) => currentVol >= f.startVol && currentVol < f.endVol);
      if (targetFrac) {
        this._selectRange(this.dragStartFraction, targetFrac);
      }
    }

    this.render();
  }

  /**
   * Clears hover indicators when mouse exits canvas.
   * @role Mouse Exit Handler
   * @private
   * @returns {void}
   */
  _handleMouseLeave() {
    this.hoverPoint = null;
    this.isDragging = false;
    this.render();
  }

  /**
   * Handles fraction track clicking and drag selection start.
   * @role Mouse Down Handler
   * @private
   * @param {MouseEvent} e - Mouse event
   * @returns {void}
   */
  _handleMouseDown(e) {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const s = this._getScales();

    // Check fraction track (top track: y between 16 and 38)
    const vol = s.pxToX(x);
    const clickedFrac = this.fractions.find((f) => vol >= f.startVol && vol < f.endVol);

    if (clickedFrac) {
      if (e.shiftKey) {
        // Toggle single fraction
        if (this.selectedFractionIds.has(clickedFrac.id)) {
          this.selectedFractionIds.delete(clickedFrac.id);
        } else {
          this.selectedFractionIds.add(clickedFrac.id);
        }
      } else {
        // Start drag or select single
        this.isDragging = true;
        this.dragStartFraction = clickedFrac;
        this.selectedFractionIds = new Set([clickedFrac.id]);
      }
      this._emitSelectionChange();
      this.render();
    }
  }

  /**
   * Finalizes fraction dragging.
   * @role Mouse Up Handler
   * @private
   * @returns {void}
   */
  _handleMouseUp() {
    if (this.isDragging) {
      this.isDragging = false;
      this.dragStartFraction = null;
      this._emitSelectionChange();
      this.render();
    }
  }

  /**
   * Selects all fractions within the range of two boundary fractions.
   * @role Range Selection Algorithm
   * @private
   * @param {FPLCFraction} f1 - Start boundary fraction
   * @param {FPLCFraction} f2 - End boundary fraction
   * @returns {void}
   */
  _selectRange(f1, f2) {
    const minVol = Math.min(f1.startVol, f2.startVol);
    const maxVol = Math.max(f1.endVol, f2.endVol);

    this.selectedFractionIds.clear();
    for (const f of this.fractions) {
      if (f.startVol >= minVol && f.endVol <= maxVol) {
        this.selectedFractionIds.add(f.id);
      }
    }
  }

  /**
   * Notifies external listeners of fraction selection changes.
   * @role Reactive Notification Dispatcher
   * @private
   * @returns {void}
   */
  _emitSelectionChange() {
    const stats = this.getPooledStats();
    if (typeof this.options.onSelectionChange === 'function') {
      this.options.onSelectionChange(stats);
    }
  }

  /**
   * Calculates pooled volume, integrated UV, and estimated protein concentration.
   * @role Stoichiometric Pooling Calculation
   * @returns {Object} Calculated pool metrics
   */
  getPooledStats() {
    const selected = this.fractions.filter((f) => this.selectedFractionIds.has(f.id));
    selected.sort((a, b) => a.startVol - b.startVol);

    const count = selected.length;
    const totalVolumeMl = count * 2.0; // 2.0 mL per tube
    let weightedUV = 0;

    for (const f of selected) {
      weightedUV += f.avgUV280 * f.volume;
    }
    const avgUV280 = totalVolumeMl > 0 ? weightedUV / totalVolumeMl : 0;

    // Beer-Lambert protein concentration:
    // A = epsilon * c * l -> c (mg/mL) = A / (epsilon * l)
    // For T7 RNAP: epsilon ~ 1.40 mL/(mg*cm), ÄKTA flow cell path ~ 0.2 cm
    // Note: ÄKTA UV is measured in mAU = 0.001 AU
    const absAU = avgUV280 / 1000.0;
    const pathCm = this.options.pathLengthCm;
    const eps = this.options.extinctionCoefficient;
    const estConcMgMl = totalVolumeMl > 0 ? (absAU / (eps * pathCm)) : 0;
    const totalYieldMg = estConcMgMl * totalVolumeMl;

    return {
      fractionIds: selected.map((f) => f.id),
      fractionRange: count > 0 ? `${selected[0].id} – ${selected[count - 1].id}` : 'None',
      count,
      totalVolumeMl: +totalVolumeMl.toFixed(1),
      avgUV280mAU: +avgUV280.toFixed(1),
      estimatedConcMgMl: +estConcMgMl.toFixed(2),
      totalYieldMg: +totalYieldMg.toFixed(2)
    };
  }

  /**
   * Dispatches the pool creation action to create a pooled entity in LIMS and Gel.
   * @role High-Level Action Trigger
   * @param {string} [poolName] - Custom pool label
   * @returns {Object} Created pool entity metadata
   */
  poolSelectedFractions(poolName = 'T7 RNAP Ni-NTA Elution Pool') {
    const stats = this.getPooledStats();
    if (stats.count === 0) {
      throw new Error('Cannot pool: No fractions selected.');
    }

    const poolEntity = {
      poolId: `POOL-${Date.now().toString(36).toUpperCase()}`,
      name: poolName,
      sourceRun: 'AKTA-AVANT-2026-T7-01',
      fractions: stats.fractionIds,
      fractionRange: stats.fractionRange,
      totalVolumeMl: stats.totalVolumeMl,
      concentrationMgMl: stats.estimatedConcMgMl,
      totalYieldMg: stats.totalYieldMg,
      timestamp: new Date().toISOString(),
      recommendedAliquotVolumeUl: 50,
      targetFreezerBox: 'B-07'
    };

    if (typeof this.options.onPoolSelected === 'function') {
      this.options.onPoolSelected(poolEntity);
    }

    return poolEntity;
  }

  /**
   * Exports current chromatogram canvas as a high-resolution PNG data URL.
   * @role Publication Figure Export
   * @returns {string} PNG Base64 data URL
   */
  exportPNG() {
    return this.canvas.toDataURL('image/png');
  }

  /**
   * Exports chromatographic run data as a CSV text payload.
   * @role Tabular Data Exporter
   * @returns {string} CSV format data
   */
  exportCSV() {
    let csv = 'Volume_mL,UV280_mAU,Conductivity_mS_cm,Percent_B\n';
    for (let i = 0; i < this.data.volumes.length; i++) {
      csv += `${this.data.volumes[i]},${this.data.uv280[i]},${this.data.conductivity[i]},${this.data.percentB[i]}\n`;
    }
    return csv;
  }
}
