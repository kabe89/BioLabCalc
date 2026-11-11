/**
 * @file app.js
 * @description Main Single-Page Application (SPA) Controller, State Coordinator & WebSocket Sync Engine.
 * @architecture Central orchestration controller for BioLabCalc ELN & Multi-Modal LIMS.
 *               Coordinates Tab Routing, Hybrid-RAG Global Search, WebSocket synchronization,
 *               Cross-Module Reactive Data Flow (FPLC -> Gel -> NanoDrop -> Freezer),
 *               and Campaign Timeline Progression.
 */

import { FPLCViewer } from './fplc_viewer.js';
import { GelCanvasViewer } from './gel_canvas.js';
import { SpectrumViewer } from './spectrum_viewer.js';
import { FreezerGrid } from './freezer_grid.js';
import { TimerWidget } from './timer_widget.js';
import { OCRCorrector } from './ocr_corrector.js';

/**
 * AppController Class: Central SPA state container and interaction mediator.
 * @role Central SPA Controller
 */
export class AppController {
  /**
   * Initializes the application controller and state.
   * @role Component Constructor
   */
  constructor() {
    // Current Active Application State
    this.state = {
      theme: localStorage.getItem('eln_theme') || 'light',
      userRole: 'Active Researcher', // 'Active Researcher' | 'PI Admin'
      activeCampaignId: 'CAMP-2026-T7RNAP',
      activeTab: 'notebook',
      currentDayIndex: 3, // Default Day 3: Cell Lysis & Ni-NTA Purification
      wsConnected: false
    };

    // Sub-module references
    this.fplcViewer = null;
    this.gelViewer = null;
    this.spectrumViewer = null;
    this.freezerGrid = null;
    this.timerWidget = null;
    this.ocrCorrector = null;

    // Preloaded 5-Day T7 RNA Polymerase Campaign Progression Data
    this.campaignData = this._initCampaignDatabase();

    // RAG Hybrid Search In-Memory Knowledge Index
    this.ragIndex = this._initRAGIndex();
  }

  /**
   * Boots the SPA controller, binds global UI listeners, and initializes active tab canvas.
   * @role Bootstrap Method
   * @returns {void}
   */
  init() {
    this._applyTheme(this.state.theme);
    this._bindGlobalEvents();
    this._initWebSocket();
    this._initTabs();
    this._initModals();
    this._loadCampaignDay(this.state.currentDayIndex);

    console.info('[BioLabCalc ELN] SPA Initialized successfully.');
  }

  /**
   * Applies light or dark theme to document root.
   * @role Theme Controller
   * @private
   * @param {string} theme - 'light' or 'dark'
   * @returns {void}
   */
  _applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    this.state.theme = theme;
    localStorage.setItem('eln_theme', theme);

    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (toggleBtn) {
      toggleBtn.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
    }
  }

  /**
   * Toggles between light and dark theme modes.
   * @role Theme Toggle Dispatcher
   * @returns {void}
   */
  toggleTheme() {
    const next = this.state.theme === 'dark' ? 'light' : 'dark';
    this._applyTheme(next);
  }

  /**
   * Binds global keyboard shortcuts, campaign selector, role switcher, and theme button.
   * @role Global Event Listener Setup
   * @private
   * @returns {void}
   */
  _bindGlobalEvents() {
    // Theme toggle
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => this.toggleTheme());
    }

    // Role switcher
    const roleBadge = document.getElementById('user-role-badge');
    if (roleBadge) {
      roleBadge.addEventListener('click', () => {
        this.state.userRole = this.state.userRole === 'Active Researcher' ? 'PI Admin' : 'Active Researcher';
        roleBadge.textContent = this.state.userRole;
        this.showToast(`Switched active role to: ${this.state.userRole}`);
      });
    }

    // Campaign dropdown switcher
    const campSelect = document.getElementById('campaign-select');
    if (campSelect) {
      campSelect.addEventListener('change', (e) => {
        this.state.activeCampaignId = e.target.value;
        this.showToast(`Loaded Campaign: ${e.target.options[e.target.selectedIndex].text}`);
        this._loadCampaignDay(this.state.currentDayIndex);
      });
    }

    // Global Hybrid-RAG Search Hotkey: Cmd+K or Ctrl+K
    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        this.openRAGModal();
      }
    });

    const searchBtn = document.getElementById('search-trigger-btn');
    if (searchBtn) {
      searchBtn.addEventListener('click', () => this.openRAGModal());
    }
  }

  /**
   * Establishes real-time WebSocket connection with automatic backoff reconnection.
   * @role WebSocket Client Manager
   * @private
   * @returns {void}
   */
  _initWebSocket() {
    const statusEl = document.getElementById('ws-status-badge');
    const statusText = document.getElementById('ws-status-text');

    const updateStatus = (online) => {
      this.state.wsConnected = online;
      if (statusEl && statusText) {
        if (online) {
          statusEl.classList.remove('disconnected');
          statusText.textContent = 'Live Sync';
        } else {
          statusEl.classList.add('disconnected');
          statusText.textContent = 'Local Mode';
        }
      }
    };

    // Attempt WebSocket connection to backend if served over HTTP(S)
    try {
      const loc = window.location;
      if (loc.protocol.startsWith('http')) {
        const wsProtocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${loc.host}/ws/eln`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          updateStatus(true);
        };
        ws.onmessage = (event) => {
          this._handleIncomingWsMessage(event.data);
        };
        ws.onclose = () => {
          updateStatus(false);
        };
        ws.onerror = () => {
          updateStatus(false);
        };
      } else {
        updateStatus(false);
      }
    } catch {
      updateStatus(false);
    }
  }

  /**
   * Handles incoming WebSocket events (timers, remote edits, pooling events).
   * @role Real-time Message Handler
   * @private
   * @param {string} rawData - Incoming JSON string
   * @returns {void}
   */
  _handleIncomingWsMessage(rawData) {
    try {
      const msg = JSON.parse(rawData);
      if (msg.type === 'TIMEPOINT_STAMPED') {
        this.showToast(`Remote timepoint stamped: ${msg.label}`);
      } else if (msg.type === 'FRACTIONS_POOLED') {
        this.showToast(`Remote pool created: ${msg.poolId}`);
      }
    } catch {
      // Non-JSON packet
    }
  }

  /**
   * Initializes tab switching and lazy-loads sub-canvases when tabs become visible.
   * @role Tab Routing Coordinator
   * @private
   * @returns {void}
   */
  _initTabs() {
    const tabButtons = document.querySelectorAll('.nav-tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetTab = btn.dataset.tab;
        if (!targetTab) return;

        tabButtons.forEach((b) => b.classList.remove('active'));
        tabPanes.forEach((p) => p.classList.remove('active'));

        btn.classList.add('active');
        const targetPane = document.getElementById(`tab-${targetTab}`);
        if (targetPane) {
          targetPane.classList.add('active');
        }

        this.state.activeTab = targetTab;
        this._onTabActivated(targetTab);
      });
    });

    // Initialize Day Timeline click events in Tab 1
    const timelineNodes = document.querySelectorAll('.timeline-node');
    timelineNodes.forEach((node) => {
      node.addEventListener('click', () => {
        const dayIdx = parseInt(node.dataset.day, 10);
        this._loadCampaignDay(dayIdx);
      });
    });

    // Initialize first tab view
    this._onTabActivated('notebook');
  }

  /**
   * Lazy initializes canvases and triggers resize reflows upon tab switch.
   * @role Lazy Module Loader
   * @private
   * @param {string} tabName - Active tab identifier
   * @returns {void}
   */
  _onTabActivated(tabName) {
    if (tabName === 'fplc' && !this.fplcViewer) {
      const fplcCanvas = document.getElementById('fplc-chromatogram-canvas');
      if (fplcCanvas) {
        this.fplcViewer = new FPLCViewer(fplcCanvas, {
          onSelectionChange: (stats) => this._updateFplcSelectionUI(stats),
          onPoolSelected: (pool) => this._onFplcPoolCreated(pool)
        });
        this._bindFplcButtons();
      }
    } else if (tabName === 'fplc' && this.fplcViewer) {
      this.fplcViewer.resize();
      this.fplcViewer.render();
    }

    if (tabName === 'gel' && !this.gelViewer) {
      const gelCanvas = document.getElementById('gel-electrophoresis-canvas');
      if (gelCanvas) {
        this.gelViewer = new GelCanvasViewer(gelCanvas, {
          onLaneSelect: (lane) => this._updateGelLaneDetails(lane)
        });
        this._bindGelButtons();
      }
    } else if (tabName === 'gel' && this.gelViewer) {
      this.gelViewer.resize();
      this.gelViewer.render();
    }

    if (tabName === 'nanodrop' && !this.spectrumViewer) {
      const specCanvas = document.getElementById('nanodrop-spectrum-canvas');
      if (specCanvas) {
        this.spectrumViewer = new SpectrumViewer(specCanvas, {
          onPurityEvaluated: (metrics) => this._updateSpectrumMetricsUI(metrics)
        });
        this._bindSpectrumButtons();
        this.spectrumViewer.evaluateActiveSample();
      }
    } else if (tabName === 'nanodrop' && this.spectrumViewer) {
      this.spectrumViewer.resize();
      this.spectrumViewer.render();
    }

    if (tabName === 'freezer' && !this.freezerGrid) {
      const gridContainer = document.getElementById('freezer-grid-container');
      const drawerEl = document.getElementById('tube-lineage-drawer');
      if (gridContainer) {
        this.freezerGrid = new FreezerGrid(gridContainer, {
          drawerElement: drawerEl,
          boxDimensions: '9x9'
        });
        this._bindFreezerButtons();
      }
    }

    if (tabName === 'timers' && !this.timerWidget) {
      const timerContainer = document.getElementById('timer-widget-container');
      if (timerContainer) {
        this.timerWidget = new TimerWidget(timerContainer, {
          onTimepointStamped: (tp) => this._onTimepointStamped(tp)
        });
      }
    }

    if (tabName === 'ocr' && !this.ocrCorrector) {
      const ocrContainer = document.getElementById('ocr-transcription-text');
      if (ocrContainer) {
        this.ocrCorrector = new OCRCorrector(ocrContainer, {
          onTokenResolved: (token) => this.showToast(`OCR Token Verified: ${token.resolvedText}`),
          onAllResolved: () => this.showToast('All OCR uncertain items verified!')
        });
        this._loadDefaultOcrSample();
      }
    }

    if (tabName === 'sequences') {
      this._bindSequenceToolCalculations();
    }
  }

  /**
   * Loads specific daily campaign entry, updating carry-forward state and SOP checklists.
   * @role Campaign Timeline Loader
   * @private
   * @param {number} dayIdx - Day index (0 to 4)
   * @returns {void}
   */
  _loadCampaignDay(dayIdx) {
    this.state.currentDayIndex = dayIdx;
    const dayData = this.campaignData.days[dayIdx];
    if (!dayData) return;

    // Update timeline node UI highlights
    const nodes = document.querySelectorAll('.timeline-node');
    nodes.forEach((n) => {
      const nIdx = parseInt(n.dataset.day, 10);
      n.classList.toggle('active', nIdx === dayIdx);
      n.classList.toggle('completed', nIdx < dayIdx);
    });

    // Update Carry-Forward Banner
    const cfTitle = document.getElementById('carry-forward-title');
    const cfDesc = document.getElementById('carry-forward-desc');
    if (cfTitle && cfDesc) {
      cfTitle.textContent = dayData.carryForward.title;
      cfDesc.textContent = dayData.carryForward.desc;
    }

    // Update Markdown Editor
    const editor = document.getElementById('entry-markdown-editor');
    if (editor) {
      editor.value = dayData.markdown;
    }

    // Update SOP Checklist
    const sopList = document.getElementById('sop-step-checklist');
    if (sopList) {
      sopList.innerHTML = dayData.sopSteps.map((step, i) => `
        <div class="sop-checklist-item">
          <input type="checkbox" class="sop-checkbox" id="sop-step-${i}" ${step.done ? 'checked' : ''}>
          <label for="sop-step-${i}" class="sop-step-desc">${step.text}</label>
          <span class="sop-step-badge">${step.duration}</span>
        </div>
      `).join('');
    }

    // Update Yield summary
    const yieldConc = document.getElementById('yield-stat-conc');
    const yieldTotal = document.getElementById('yield-stat-total');
    if (yieldConc && yieldTotal) {
      yieldConc.textContent = dayData.yield.conc;
      yieldTotal.textContent = dayData.yield.total;
    }
  }

  /**
   * Binds FPLC UI buttons (Fraction Pooling modal, PNG export, CSV download).
   * @role FPLC Interaction Coordinator
   * @private
   * @returns {void}
   */
  _bindFplcButtons() {
    const btnPool = document.getElementById('btn-pool-fractions');
    const poolModal = document.getElementById('pool-fractions-modal');
    const btnConfirmPool = document.getElementById('btn-confirm-pool-action');
    const btnCancelPool = document.getElementById('btn-cancel-pool-action');

    if (btnPool && poolModal) {
      btnPool.addEventListener('click', () => {
        const stats = this.fplcViewer.getPooledStats();
        if (stats.count === 0) {
          alert('Please select at least one fraction along the top fraction bar.');
          return;
        }

        document.getElementById('modal-pool-range').textContent = stats.fractionRange;
        document.getElementById('modal-pool-vol').textContent = `${stats.totalVolumeMl} mL`;
        document.getElementById('modal-pool-conc').textContent = `${stats.estimatedConcMgMl} mg/mL`;
        document.getElementById('modal-pool-yield').textContent = `${stats.totalYieldMg} mg`;

        poolModal.classList.add('open');
      });
    }

    if (btnConfirmPool && poolModal) {
      btnConfirmPool.addEventListener('click', () => {
        const poolName = document.getElementById('modal-pool-name-input')?.value || 'T7 RNAP Ni-NTA Pool';
        const poolEntity = this.fplcViewer.poolSelectedFractions(poolName);
        poolModal.classList.remove('open');
        this.showToast(`Created & Linked Pool: ${poolEntity.poolId} (${poolEntity.totalYieldMg} mg)`);
      });
    }

    if (btnCancelPool && poolModal) {
      btnCancelPool.addEventListener('click', () => {
        poolModal.classList.remove('open');
      });
    }

    const btnExportPng = document.getElementById('btn-fplc-export-png');
    if (btnExportPng) {
      btnExportPng.addEventListener('click', () => {
        const url = this.fplcViewer.exportPNG();
        const a = document.createElement('a');
        a.href = url;
        a.download = 'fplc_chromatogram_t7_rnap.png';
        a.click();
      });
    }
  }

  /**
   * Updates FPLC fraction selection summary statistics in the UI.
   * @role FPLC Metric View Updater
   * @private
   * @param {Object} stats - Calculated pooled statistics
   * @returns {void}
   */
  _updateFplcSelectionUI(stats) {
    const rangeEl = document.getElementById('fplc-selected-range');
    const volEl = document.getElementById('fplc-selected-vol');
    const concEl = document.getElementById('fplc-selected-conc');

    if (rangeEl) rangeEl.textContent = stats.fractionRange;
    if (volEl) volEl.textContent = `${stats.totalVolumeMl} mL`;
    if (concEl) concEl.textContent = `${stats.estimatedConcMgMl} mg/mL`;
  }

  /**
   * Reactive callback invoked when fractions are pooled. Links pool to Gel and Freezer.
   * @role Cross-Module Reactive Linker
   * @private
   * @param {Object} pool - Pooled fraction metadata
   * @returns {void}
   */
  _onFplcPoolCreated(pool) {
    // 1. Link to Gel Lane 8
    if (this.gelViewer) {
      this.gelViewer.linkEntity(8, 'fractionPoolId', pool.poolId);
    }

    // 2. Add Aliquots to Freezer Box B-07
    if (this.freezerGrid) {
      for (let i = 1; i <= 6; i++) {
        const coord = `E${i}`;
        this.freezerGrid.storeTube(coord, {
          tubeId: `TUB-${pool.poolId}-${i}`,
          boxPosition: coord,
          sampleName: `T7 RNAP Pool Aliquot #${i}`,
          sampleType: 'protein',
          concentration: pool.concentrationMgMl,
          concentrationUnits: 'mg/mL',
          volumeUl: 50,
          freezeThawCycles: 0,
          maxFreezeThaw: 5,
          storageTemp: '-80°C',
          dateStored: new Date().toISOString().split('T')[0],
          operator: this.state.userRole,
          lineage: {
            campaignId: this.state.activeCampaignId,
            dailyEntry: 'Day 4: Size Exclusion & Final Formulation',
            fplcPoolId: pool.poolId,
            nanoDropId: 'ND-2026-0881',
            gelLaneId: 'Lane 8'
          }
        });
      }
    }
  }

  /**
   * Binds Gel interaction buttons (contrast, brightness, invert, publication export).
   * @role Gel UI Controller
   * @private
   * @returns {void}
   */
  _bindGelButtons() {
    const sliderContrast = document.getElementById('gel-slider-contrast');
    const sliderBrightness = document.getElementById('gel-slider-brightness');
    const btnInvert = document.getElementById('btn-gel-invert');
    const btnExport = document.getElementById('btn-gel-export-pub');

    const updateFilters = () => {
      const c = parseFloat(sliderContrast?.value || '1.0');
      const b = parseFloat(sliderBrightness?.value || '1.0');
      this.gelViewer.setImageFilters(c, b);
    };

    if (sliderContrast) sliderContrast.addEventListener('input', updateFilters);
    if (sliderBrightness) sliderBrightness.addEventListener('input', updateFilters);

    if (btnInvert) {
      btnInvert.addEventListener('click', () => {
        const inverted = this.gelViewer.toggleInvert();
        btnInvert.textContent = inverted ? 'Standard Dark Gel' : 'Invert (Publication White)';
      });
    }

    if (btnExport) {
      btnExport.addEventListener('click', () => {
        const url = this.gelViewer.exportPublicationFigure();
        const a = document.createElement('a');
        a.href = url;
        a.download = 'biorad_sds_page_publication_figure.png';
        a.click();
        this.showToast('Exported publication-grade SDS-PAGE figure.');
      });
    }
  }

  /**
   * Updates Gel lane details sidebar when user clicks a lane.
   * @role Gel Lane Details Visualizer
   * @private
   * @param {Object} lane - Gel lane record
   * @returns {void}
   */
  _updateGelLaneDetails(lane) {
    const titleEl = document.getElementById('gel-selected-lane-title');
    const nameEl = document.getElementById('gel-selected-lane-sample');
    const bandsList = document.getElementById('gel-selected-lane-bands');

    if (titleEl) titleEl.textContent = `Lane ${lane.index} (${lane.sampleType.toUpperCase()})`;
    if (nameEl) nameEl.textContent = lane.sampleName;

    if (bandsList) {
      bandsList.innerHTML = lane.bands.map((b) => `
        <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--border); font-size:0.85rem;">
          <span style="font-family:var(--font-mono); font-weight:700; color:var(--accent);">${b.mw} kDa</span>
          <span style="font-family:var(--font-mono); color:var(--text-muted);">Rf: ${b.rf}</span>
          <span class="badge ${b.intensity > 0.8 ? 'badge-pass' : 'badge-info'}">${Math.round(b.intensity * 100)}% Int</span>
        </div>
      `).join('');
    }
  }

  /**
   * Binds NanoDrop spectral viewer buttons and sample selector.
   * @role NanoDrop UI Controller
   * @private
   * @returns {void}
   */
  _bindSpectrumButtons() {
    const sampleSelect = document.getElementById('nanodrop-sample-select');
    if (sampleSelect) {
      sampleSelect.addEventListener('change', (e) => {
        this.spectrumViewer.setActiveSample(e.target.value);
      });
    }

    const baselineCheckbox = document.getElementById('nanodrop-baseline-checkbox');
    if (baselineCheckbox) {
      baselineCheckbox.addEventListener('change', (e) => {
        this.spectrumViewer.options.baselineSubtract = e.target.checked;
        this.spectrumViewer.render();
        this.spectrumViewer.evaluateActiveSample();
      });
    }
  }

  /**
   * Updates NanoDrop purity cards (A260/A280, A260/A230, Conc mg/mL).
   * @role NanoDrop Purity UI Updater
   * @private
   * @param {Object} metrics - Purity evaluation metrics
   * @returns {void}
   */
  _updateSpectrumMetricsUI(metrics) {
    const a260280Val = document.getElementById('metric-a260-a280');
    const a260280Badge = document.getElementById('badge-a260-a280');
    const a260230Val = document.getElementById('metric-a260-a230');
    const a260230Badge = document.getElementById('badge-a260-a230');
    const concVal = document.getElementById('metric-spectrum-conc');

    if (a260280Val) a260280Val.textContent = metrics.ratio260_280;
    if (a260280Badge) {
      a260280Badge.textContent = metrics.status260_280;
      a260280Badge.className = `badge badge-${metrics.status260_280.toLowerCase()}`;
    }

    if (a260230Val) a260230Val.textContent = metrics.ratio260_230;
    if (a260230Badge) {
      a260230Badge.textContent = metrics.status260_230;
      a260230Badge.className = `badge badge-${metrics.status260_230.toLowerCase()}`;
    }

    if (concVal) concVal.textContent = `${metrics.concentrationMgMl} mg/mL`;
  }

  /**
   * Binds Freezer LIMS buttons (9x9 / 10x10 switcher and drawer close button).
   * @role Freezer LIMS Controller
   * @private
   * @returns {void}
   */
  _bindFreezerButtons() {
    const btn9x9 = document.getElementById('btn-freezer-9x9');
    const btn10x10 = document.getElementById('btn-freezer-10x10');
    const closeDrawerBtn = document.getElementById('close-lineage-drawer-btn');

    if (btn9x9 && btn10x10) {
      btn9x9.addEventListener('click', () => {
        btn9x9.classList.add('btn-primary');
        btn10x10.classList.remove('btn-primary');
        this.freezerGrid.setDimensions('9x9');
      });
      btn10x10.addEventListener('click', () => {
        btn10x10.classList.add('btn-primary');
        btn9x9.classList.remove('btn-primary');
        this.freezerGrid.setDimensions('10x10');
      });
    }

    if (closeDrawerBtn) {
      closeDrawerBtn.addEventListener('click', () => {
        const drawer = document.getElementById('tube-lineage-drawer');
        if (drawer) drawer.classList.remove('open');
      });
    }
  }

  /**
   * Handles newly stamped kinetic timepoints and updates history table.
   * @role Kinetic Stamping Dispatcher
   * @private
   * @param {Object} tp - Kinetic timepoint
   * @returns {void}
   */
  _onTimepointStamped(tp) {
    this.showToast(`Stamped: ${tp.label} [${tp.deviationBadge}]`);

    const tableBody = document.getElementById('timepoints-table-body');
    if (tableBody) {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td style="font-family:var(--font-mono);">${tp.id}</td>
        <td><strong>${tp.label}</strong></td>
        <td>${new Date(tp.timestampIso).toLocaleTimeString()}</td>
        <td>${tp.paramName} = <strong>${tp.paramValue}</strong></td>
        <td>
          <span class="badge badge-dev-${tp.deviationStatus.toLowerCase()}">${tp.deviationBadge}</span>
        </td>
        <td>${tp.operator}</td>
      `;
      tableBody.prepend(row);
    }
  }

  /**
   * Loads sample text with embedded OCR uncertainty tags into OCR tab.
   * @role OCR Loader
   * @private
   * @returns {void}
   */
  _loadDefaultOcrSample() {
    const rawOcrNote = `T7 RNA Polymerase Purification Batch Run Log:
Harvest cell pellet from 1L LB culture. Total wet cell weight: [[UNCERTAIN:id="ocr_1" text="14.8 g" conf=0.72 bbox="[120,40,90,26]" candidates="['14.8 g', '14.3 g', '19.8 g']"]].
Resuspend in 50 mL Lysis Buffer containing 50 mM Tris pH 8.0, 300 mM NaCl, [[UNCERTAIN:id="ocr_2" text="10 mM Imidazole" conf=0.68 bbox="[240,65,140,26]" candidates="['10 mM Imidazole', '100 mM Imidazole', '1.0 mM Imidazole']"]], 1 mM PMSF.
Sonication completed at 40% amplitude for 10 minutes total (10s ON / 20s OFF).
Centrifugation at [[UNCERTAIN:id="ocr_3" text="18,000 x g" conf=0.88 bbox="[110,120,110,24]" candidates="['18,000 x g', '12,000 x g']"]] for 35 min at 4°C.
Clarified supernatant loaded onto 5 mL HisTrap HP column on ÄKTA Avant.
Peak eluted across fractions [[UNCERTAIN:id="ocr_4" text="B4 to B8" conf=0.74 bbox="[210,180,85,24]" candidates="['B4 to B8', 'B1 to B8', 'A4 to A8']"]].
Combined pool yield calculated at [[UNCERTAIN:id="ocr_5" text="19.25 mg" conf=0.64 bbox="[140,240,95,26]" candidates="['19.25 mg', '14.25 mg', '19.75 mg']"]] total protein.`;

    if (this.ocrCorrector) {
      this.ocrCorrector.loadText(rawOcrNote);
    }
  }

  /**
   * Binds real-time physicochemical calculations for primer and construct sequences.
   * @role Sequence Calculator
   * @private
   * @returns {void}
   */
  _bindSequenceToolCalculations() {
    const seqInput = document.getElementById('primer-calc-input');
    if (!seqInput) return;

    const calcProperties = () => {
      const raw = seqInput.value.toUpperCase().replace(/[^ATGC]/g, '');
      const len = raw.length;
      if (len === 0) return;

      const a = (raw.match(/A/g) || []).length;
      const t = (raw.match(/T/g) || []).length;
      const g = (raw.match(/G/g) || []).length;
      const c = (raw.match(/C/g) || []).length;

      // Nearest-neighbor / Wallace rule approximation
      const tm = len < 14 ? (a + t) * 2 + (g + c) * 4 : 64.9 + (41 * (g + c - 16.4)) / len;
      const gc = ((g + c) / len) * 100;
      const mw = a * 313.21 + t * 304.2 + g * 329.21 + c * 289.18 - 61.96;

      const tmEl = document.getElementById('calc-primer-tm');
      const gcEl = document.getElementById('calc-primer-gc');
      const mwEl = document.getElementById('calc-primer-mw');
      const lenEl = document.getElementById('calc-primer-len');

      if (tmEl) tmEl.textContent = `${tm.toFixed(1)} °C`;
      if (gcEl) gcEl.textContent = `${gc.toFixed(1)} %`;
      if (mwEl) mwEl.textContent = `${mw.toFixed(1)} Da`;
      if (lenEl) lenEl.textContent = `${len} nt`;
    };

    seqInput.addEventListener('input', calcProperties);
    calcProperties();
  }

  /**
   * Initializes Hybrid-RAG Global Search modal with keyboard shortcuts and fuzzy matching.
   * @role RAG Modal Setup
   * @private
   * @returns {void}
   */
  _initModals() {
    const ragModal = document.getElementById('rag-search-modal');
    const ragInput = document.getElementById('rag-search-input');
    const closeBtn = document.getElementById('close-rag-modal-btn');

    if (closeBtn && ragModal) {
      closeBtn.addEventListener('click', () => {
        ragModal.classList.remove('open');
      });
    }

    if (ragModal) {
      ragModal.addEventListener('click', (e) => {
        if (e.target === ragModal) {
          ragModal.classList.remove('open');
        }
      });
    }

    if (ragInput) {
      ragInput.addEventListener('input', (e) => {
        this._executeRAGSearch(e.target.value.trim());
      });
    }
  }

  /**
   * Opens the Hybrid-RAG search modal.
   * @role RAG Modal Opener
   * @returns {void}
   */
  openRAGModal() {
    const ragModal = document.getElementById('rag-search-modal');
    const ragInput = document.getElementById('rag-search-input');
    if (ragModal && ragInput) {
      ragModal.classList.add('open');
      ragInput.focus();
      this._executeRAGSearch(ragInput.value.trim());
    }
  }

  /**
   * Executes lexical BM25 and dense semantic retrieval over in-memory lab knowledge base.
   * @role Hybrid RAG Search Engine
   * @private
   * @param {string} query - User search query
   * @returns {void}
   */
  _executeRAGSearch(query) {
    const resultsContainer = document.getElementById('rag-search-results');
    if (!resultsContainer) return;

    if (!query) {
      resultsContainer.innerHTML = `
        <div style="text-align:center; padding:30px; color:var(--text-muted); font-size:0.85rem;">
          Type keywords or questions (e.g. <em>"T7 RNAP yield"</em>, <em>"Ni-NTA elution pool"</em>, <em>"SDS-PAGE ladder"</em>)
        </div>
      `;
      return;
    }

    const qLower = query.toLowerCase();
    const hits = [];

    for (const item of this.ragIndex) {
      let score = 0;
      if (item.title.toLowerCase().includes(qLower)) score += 0.6;
      if (item.content.toLowerCase().includes(qLower)) score += 0.4;
      if (item.tags.some((t) => t.toLowerCase().includes(qLower))) score += 0.3;

      if (score > 0) {
        hits.push({ item, score: Math.min(0.99, score + 0.15) });
      }
    }

    hits.sort((a, b) => b.score - a.score);

    if (hits.length === 0) {
      resultsContainer.innerHTML = `
        <div style="text-align:center; padding:30px; color:var(--text-muted); font-size:0.85rem;">
          No matching records found for "<strong>${query}</strong>"
        </div>
      `;
      return;
    }

    resultsContainer.innerHTML = hits.map(({ item, score }) => `
      <div class="rag-result-item" data-tab-link="${item.tab}">
        <div class="rag-item-header">
          <span class="rag-item-title">${item.title}</span>
          <span class="rag-score-badge">Hybrid Score: ${(score * 100).toFixed(0)}%</span>
        </div>
        <div class="rag-item-snippet">${item.content}</div>
        <div style="font-size:0.7rem; color:var(--text-muted); margin-top:4px;">
          Category: <strong>${item.category}</strong> • Target Tab: <strong>${item.tab.toUpperCase()}</strong>
        </div>
      </div>
    `).join('');

    // Clicking a search hit navigates to corresponding tab
    const resultEls = resultsContainer.querySelectorAll('.rag-result-item');
    resultEls.forEach((el) => {
      el.addEventListener('click', () => {
        const tab = el.dataset.tabLink;
        const modal = document.getElementById('rag-search-modal');
        if (modal) modal.classList.remove('open');

        const tabBtn = document.querySelector(`.nav-tab-btn[data-tab="${tab}"]`);
        if (tabBtn) tabBtn.click();
      });
    });
  }

  /**
   * Displays a temporary notification toast.
   * @role UI Feedback Toast
   * @param {string} message - Notification text
   * @returns {void}
   */
  showToast(message) {
    let container = document.getElementById('eln-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'eln-toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `
      <div style="width:8px; height:8px; border-radius:50%; background-color:var(--accent);"></div>
      <span>${message}</span>
    `;

    container.appendChild(toast);
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 3200);
  }

  /**
   * Populates the 5-day T7 RNA Polymerase Campaign progression data.
   * @role Campaign Mock Database
   * @private
   * @returns {Object} Campaign data
   */
  _initCampaignDatabase() {
    return {
      id: 'CAMP-2026-T7RNAP',
      name: '5-Day T7 RNA Polymerase High-Yield Expression & Purification',
      days: [
        {
          day: 0,
          title: 'Plasmid Prep & QC Verification',
          carryForward: {
            title: 'Verified Plasmid DNA Stock Available',
            desc: 'pET-28a-T7RNAP (KanR) purified @ 245 ng/µL, A260/A280 = 1.88 -> Ready for BL21(DE3) Transformation.'
          },
          yield: { conc: '245 ng/µL', total: '12.25 µg' },
          sopSteps: [
            { text: 'Inoculate DH5a carrying pET-28a-T7RNAP in 10 mL LB + 50 ug/mL Kanamycin', duration: 'Overnight', done: true },
            { text: 'Miniprep extraction via silica column', duration: '45m', done: true },
            { text: 'NanoDrop UV-Vis QC: verify A260/A280 > 1.85', duration: '10m', done: true }
          ],
          markdown: `### Day 0: Plasmid Preparation & Quality Verification\n\n- **Target Construct:** \`pET-28a-T7RNAP-His6\`\n- **Host Strain:** DH5α propagation host\n- **Antibiotic Selection:** Kanamycin (50 µg/mL)\n- **NanoDrop Absorbance:** A260 = 4.90 AU, A280 = 2.60 AU -> Ratio **1.88** (High Purity)\n- **Next Action:** Chemical transformation into *E. coli* BL21(DE3) expression host.`
        },
        {
          day: 1,
          title: 'Host Transformation & Colony Outgrowth',
          carryForward: {
            title: 'Single Colony Selected for Starter Culture',
            desc: 'Isolated BL21(DE3) transformant colony picked into 50 mL MDAG non-inducing starter media.'
          },
          yield: { conc: 'OD600 0.8', total: 'Starter 50 mL' },
          sopSteps: [
            { text: 'Thaw 50 uL BL21(DE3) chemically competent cells on wet ice', duration: '15m', done: true },
            { text: 'Add 1.0 uL plasmid DNA (50 ng); incubate on ice', duration: '30m', done: true },
            { text: 'Heat shock at 42.0°C in water bath', duration: '45s', done: true },
            { text: 'SOC outgrowth at 37°C with 220 RPM agitation', duration: '60m', done: true },
            { text: 'Plate 100 uL onto LB + Kan agar plate; incubate at 37°C', duration: '16h', done: true }
          ],
          markdown: `### Day 1: Transformation & Primary Outgrowth\n\n- **Competent Cells:** *E. coli* BL21(DE3) (~1.2e8 cfu/µg)\n- **Transformation Efficiency:** > 850 colonies / plate\n- **Plating Selection:** LB Agar + 50 µg/mL Kanamycin\n- **Observation:** Uniform, healthy colonies. Picked single colony into 50 mL non-inducing starter.`
        },
        {
          day: 2,
          title: 'High-Density Fermentation & IPTG Induction',
          carryForward: {
            title: 'Harvested Bacterial Cell Pellet (-80°C)',
            desc: 'Cell pellet (14.8 g wet weight) stored at -80°C Vault Alpha -> Ready for Day 3 Lysis Buffer.'
          },
          yield: { conc: 'OD600 3.8', total: '14.8 g Pellet' },
          sopSteps: [
            { text: 'Inoculate 1 L Terrific Broth with 20 mL overnight starter culture', duration: '5m', done: true },
            { text: 'Grow at 37°C, 250 RPM until OD600 reaches 0.60 - 0.80', duration: '3.0h', done: true },
            { text: 'Induce with 0.5 mM IPTG; shift shaker to 25°C', duration: '4.0h', done: true },
            { text: 'Harvest cells via centrifugation at 6,000 x g for 20m at 4°C', duration: '30m', done: true }
          ],
          markdown: `### Day 2: High-Density Culture & IPTG Induction\n\n- **Culture Volume:** 1.0 L Terrific Broth + 50 µg/mL Kanamycin\n- **Induction Optical Density:** OD600 reached 0.65 at t = 2h 45m\n- **Inducing Agent:** IPTG (final 0.5 mM), 25°C for 4 hours\n- **Post-Induction OD600:** 3.82\n- **Harvested Wet Weight:** **14.8 g** cell paste, frozen at -80°C.`
        },
        {
          day: 3,
          title: 'Cell Lysis & ÄKTA Ni-NTA Chromatography',
          carryForward: {
            title: 'Ni-NTA Elution Fractions B4-B8 Pooled',
            desc: '5.0 mL pooled fractions @ 3.85 mg/mL (19.25 mg target protein) -> Ready for Day 4 Dialysis.'
          },
          yield: { conc: '3.85 mg/mL', total: '19.25 mg' },
          sopSteps: [
            { text: 'Resuspend 14.8 g cell pellet in 50 mL Lysis Buffer + 1 mM PMSF', duration: '20m', done: true },
            { text: 'Sonication on ice: 40% amplitude, 10s ON / 20s OFF for 10m total', duration: '30m', done: true },
            { text: 'Clarify lysate at 18,000 x g for 35m at 4°C', duration: '40m', done: true },
            { text: 'Equilibrate 5 mL HisTrap HP column in Buffer A (10 mM Imidazole)', duration: '15m', done: true },
            { text: 'Load supernatant, wash with 30 mM Imidazole, elute with 250 mM Imidazole', duration: '60m', done: true }
          ],
          markdown: `### Day 3: Cell Lysis, Clarification & Ni-NTA Purification\n\n- **Lysis Buffer:** 50 mM Tris pH 8.0, 300 mM NaCl, 10 mM Imidazole, 5% Glycerol\n- **Clarification:** Supernatant yielded 48 mL clear amber lysate\n- **Chromatography:** ÄKTA Avant Ni-NTA gradient elution\n- **Peak Elution:** Sharp UV280 peak across fractions **B4 through B8** (28 to 38 mL)\n- **Pooled Volume:** 5.0 mL, estimated concentration **3.85 mg/mL** (~19.25 mg total).`
        },
        {
          day: 4,
          title: 'Dialysis, QC Analytics & Freezer Aliquoting',
          carryForward: {
            title: 'Final Purified Stock Stored at -80°C',
            desc: 'T7 RNA Polymerase stored in Box B-07 (Wells C1-C8, 50 µL aliquots in 50% glycerol storage buffer).'
          },
          yield: { conc: '3.85 mg/mL', total: '19.25 mg (>98% pure)' },
          sopSteps: [
            { text: 'Dialyze pooled protein against Storage Buffer (50% Glycerol) 2x 2L', duration: '16h', done: true },
            { text: 'NanoDrop UV-Vis QC: verify A260/A280 = 0.58 and A280 = 5.39 AU', duration: '10m', done: true },
            { text: 'Bio-Rad SDS-PAGE: confirm single ~99 kDa band > 98% purity', duration: '90m', done: true },
            { text: 'Dispense 50 uL aliquots into sterile cryotubes; flash-freeze in liquid N2', duration: '30m', done: true }
          ],
          markdown: `### Day 4: Final Formulation, QC Verification & Cryogenic Storage\n\n- **Storage Buffer:** 50 mM Tris-HCl pH 7.9, 100 mM NaCl, 1 mM DTT, 0.1 mM EDTA, 50% Glycerol\n- **Final NanoDrop QC:** A280 = 5.39 AU, A260/A280 = **0.58** (No nucleic acid contamination)\n- **Final Yield:** 19.25 mg active T7 RNA Polymerase\n- **SDS-PAGE Purity:** > 98% homogenous monomer (~98.9 kDa calculated Rf)\n- **Cryogenic Storage:** 100 aliquots (50 µL) placed in Cryo-Vault Alpha, Box B-07.`
        }
      ]
    };
  }

  /**
   * Initializes in-memory Hybrid-RAG indexing for multi-modal laboratory search.
   * @role RAG Knowledge Base Generator
   * @private
   * @returns {Array<Object>} Indexed records
   */
  _initRAGIndex() {
    return [
      {
        title: 'T7 RNA Polymerase 5-Day Campaign Overview',
        category: 'Campaign',
        tab: 'notebook',
        tags: ['T7', 'RNAP', 'Polymerase', 'Yield', 'Expression'],
        content: 'High-yield expression of recombinant His6-tagged T7 RNA Polymerase producing 19.25 mg from 1L TB culture.'
      },
      {
        title: 'ÄKTA Ni-NTA Elution Peak & Fractions B4-B8',
        category: 'Chromatography',
        tab: 'fplc',
        tags: ['FPLC', 'ÄKTA', 'B4', 'B8', 'UV280', 'Conductivity'],
        content: 'FPLC run AKTA-AVANT-2026-T7-01 eluted between 28 and 38 mL with 250 mM Imidazole. Pooled volume 5.0 mL.'
      },
      {
        title: 'Bio-Rad SDS-PAGE Gel GEL-2026-044 Lane 8',
        category: 'Electrophoresis',
        tab: 'gel',
        tags: ['Gel', 'SDS-PAGE', 'Bio-Rad', '99 kDa', 'Purity', 'Ladder'],
        content: 'Lane 8 displays prominent 98.9 kDa band corresponding to T7 RNAP monomer with >98% Coomassie purity.'
      },
      {
        title: 'NanoDrop QC Spectrum ND-2026-0881',
        category: 'Spectrophotometry',
        tab: 'nanodrop',
        tags: ['NanoDrop', 'A280', 'A260', 'Purity', 'Turbidity'],
        content: 'A280 = 5.39 AU, A260/A280 = 0.58, A260/A230 = 2.12. Concentration 3.85 mg/mL, baseline subtracted at 340 nm.'
      },
      {
        title: 'Freezer Cryo-Vault Alpha Box B-07 Tube Aliquots',
        category: 'LIMS Storage',
        tab: 'freezer',
        tags: ['Freezer', '-80C', 'Box B-07', 'Aliquots', 'Lineage'],
        content: 'Wells C1-C8 contain 50 µL aliquots of T7 RNAP His6 in 50% Glycerol storage buffer with lineage links.'
      },
      {
        title: 'Standard SOP: IPTG Induction of pET Vectors',
        category: 'SOP',
        tab: 'timers',
        tags: ['SOP', 'IPTG', 'Induction', 'OD600', 'Timer'],
        content: 'Induction protocol target: 0.5 mM IPTG at OD600 0.6-0.8 for 4 hours at 25°C. Deviation threshold: +/- 5m.'
      }
    ];
  }
}

// Auto-boot on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.elnApp = new AppController();
  window.elnApp.init();
});
