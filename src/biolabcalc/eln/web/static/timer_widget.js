/**
 * @file timer_widget.js
 * @agent eln-frontend-agent
 * @description Real-Time Kinetic Countdown/Stopwatch Timers & SOP Protocol Deviation Logger.
 * @architecture High-precision web timer engine supporting dual countdown/elapsed modes,
 *               Web Audio API synthetic alerts, target duration deviation calculations (+/- mm:ss),
 *               and structured kinetic timepoint stamping for growth curves (OD600) and kinetic assays.
 */

/**
 * Represents a stamped kinetic timepoint.
 * @typedef {Object} KineticTimepoint
 * @property {string} id - Unique timepoint identifier
 * @property {string} label - Step title (e.g. 'IPTG Induction t=2h')
 * @property {string} timestampIso - ISO 8601 wall-clock timestamp
 * @property {number} targetDurationSec - Planned SOP target time in seconds
 * @property {number} actualDurationSec - Actual elapsed time in seconds
 * @property {number} deviationSec - Delta in seconds (Actual - Target)
 * @property {string} deviationBadge - Formatted string (e.g. '+01:14', '-00:30', '00:00')
 * @property {string} deviationStatus - Status flag ('PASS'|'FLAG'|'EARLY')
 * @property {number} [paramValue] - Kinetic parameter value (e.g. OD600 = 1.45)
 * @property {string} [paramName] - Kinetic parameter name (e.g. 'OD600')
 * @property {string} operator - Operator name
 */

/**
 * TimerWidget Class: Coordinates countdown timers, stopwatch, audio beeps, and timepoint logging.
 * @agent eln-frontend-agent
 * @role Kinetic laboratory timing and deviation logger
 */
export class TimerWidget {
  /**
   * Initializes the TimerWidget instance.
   * @agent eln-frontend-agent
   * @role Component Constructor
   * @param {string|HTMLElement} containerElement - Container element or ID
   * @param {Object} options - Configuration options
   * @param {number} [options.targetDurationSec=14400] - Initial target duration in seconds (default 4h = 14400s)
   * @param {string} [options.mode='countdown'] - Mode: 'countdown' or 'elapsed'
   * @param {Function} [options.onTimepointStamped] - Callback when timepoint is stamped
   * @param {Function} [options.onTimerExpired] - Callback when countdown reaches 0
   */
  constructor(containerElement, options = {}) {
    this.container = typeof containerElement === 'string' ? document.getElementById(containerElement) : containerElement;
    if (!this.container) {
      throw new Error(`[TimerWidget] Container element not found: ${containerElement}`);
    }

    this.options = Object.assign({
      targetDurationSec: 14400, // 4 hours for IPTG induction
      mode: 'countdown',
      stepName: 'IPTG Induction (0.5 mM, 37°C)',
      onTimepointStamped: null,
      onTimerExpired: null
    }, options);

    // State Variables
    this.mode = this.options.mode; // 'countdown' or 'elapsed'
    this.targetDurationSec = this.options.targetDurationSec;
    this.remainingSec = this.targetDurationSec;
    this.elapsedSec = 0;
    this.isRunning = false;
    this.timerInterval = null;
    this.startTime = null;

    // Timepoint History Log
    this.timepoints = [];

    // Web Audio Synthesizer Context (Lazy Init)
    this.audioCtx = null;

    this.render();
  }

  /**
   * Builds the interactive timer card UI and attaches DOM listeners.
   * @agent eln-frontend-agent
   * @role DOM Builder
   * @returns {void}
   */
  render() {
    this.container.innerHTML = `
      <div class="timer-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span class="badge badge-info" id="timer-step-badge">${this.options.stepName}</span>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-outline btn-sm ${this.mode === 'countdown' ? 'btn-primary' : ''}" id="mode-countdown-btn">Countdown</button>
            <button class="btn btn-outline btn-sm ${this.mode === 'elapsed' ? 'btn-primary' : ''}" id="mode-elapsed-btn">Elapsed</button>
          </div>
        </div>

        <div class="timer-display-clock" id="timer-clock-digits">
          ${this._formatTime(this.mode === 'countdown' ? this.remainingSec : this.elapsedSec)}
        </div>

        <div class="timer-target-subtext">
          Target SOP Duration: <strong id="target-duration-text">${this._formatTime(this.targetDurationSec)}</strong>
        </div>

        <div class="timer-controls-row">
          <button class="btn btn-primary" id="btn-timer-toggle">
            ${this.isRunning ? 'Pause' : 'Start Timer'}
          </button>
          <button class="btn btn-outline" id="btn-timer-reset">
            Reset
          </button>
        </div>

        <div style="background:var(--bg-app); border:1px solid var(--border); border-radius:var(--radius-md); padding:12px; margin-top:16px;">
          <div style="display:flex; gap:8px; align-items:center; margin-bottom:10px;">
            <label style="font-size:0.8rem; font-weight:600; color:var(--text-muted);">Parameter Stamp:</label>
            <input type="text" id="stamp-param-name" value="OD600" style="width:70px; padding:4px 8px; font-size:0.8rem; border:1px solid var(--border); border-radius:4px;">
            <input type="number" id="stamp-param-val" step="0.01" value="0.65" placeholder="Value" style="width:90px; padding:4px 8px; font-size:0.8rem; border:1px solid var(--border); border-radius:4px;">
          </div>
          <button class="btn btn-success" id="btn-stamp-timepoint" style="width:100%;">
            Stamp Kinetic Timepoint
          </button>
        </div>

        <!-- Presets Row -->
        <div style="display:flex; justify-content:center; gap:6px; margin-top:14px; flex-wrap:wrap;">
          <button class="btn btn-outline btn-sm preset-btn" data-sec="45" data-name="Heat Shock 42°C">45s Heat Shock</button>
          <button class="btn btn-outline btn-sm preset-btn" data-sec="1800" data-name="Sonication Lysis">30m Lysis</button>
          <button class="btn btn-outline btn-sm preset-btn" data-sec="3600" data-name="Ni-NTA Binding">60m Binding</button>
          <button class="btn btn-outline btn-sm preset-btn" data-sec="14400" data-name="IPTG Induction">4h Induction</button>
        </div>
      </div>
    `;

    this._bindDomEvents();
  }

  /**
   * Binds UI control button events.
   * @agent eln-frontend-agent
   * @role DOM Event Binder
   * @private
   * @returns {void}
   */
  _bindDomEvents() {
    const btnToggle = this.container.querySelector('#btn-timer-toggle');
    const btnReset = this.container.querySelector('#btn-timer-reset');
    const btnStamp = this.container.querySelector('#btn-stamp-timepoint');
    const btnCountdown = this.container.querySelector('#mode-countdown-btn');
    const btnElapsed = this.container.querySelector('#mode-elapsed-btn');

    if (btnToggle) {
      btnToggle.addEventListener('click', () => this.toggle());
    }
    if (btnReset) {
      btnReset.addEventListener('click', () => this.reset());
    }
    if (btnStamp) {
      btnStamp.addEventListener('click', () => {
        const paramName = this.container.querySelector('#stamp-param-name')?.value || 'OD600';
        const paramVal = parseFloat(this.container.querySelector('#stamp-param-val')?.value || '0.0');
        this.stampTimepoint(this.options.stepName, paramName, paramVal);
      });
    }

    if (btnCountdown) {
      btnCountdown.addEventListener('click', () => {
        this.mode = 'countdown';
        this.render();
      });
    }
    if (btnElapsed) {
      btnElapsed.addEventListener('click', () => {
        this.mode = 'elapsed';
        this.render();
      });
    }

    // Presets
    const presetBtns = this.container.querySelectorAll('.preset-btn');
    presetBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const sec = parseInt(btn.dataset.sec, 10);
        const name = btn.dataset.name;
        this.setPreset(sec, name);
      });
    });
  }

  /**
   * Starts or pauses the active timer.
   * @agent eln-frontend-agent
   * @role Timer Execution Controller
   * @returns {void}
   */
  toggle() {
    if (this.isRunning) {
      this.pause();
    } else {
      this.start();
    }
  }

  /**
   * Starts timer countdown or stopwatch ticks.
   * @agent eln-frontend-agent
   * @role Timer Start Engine
   * @returns {void}
   */
  start() {
    if (this.isRunning) return;
    this.isRunning = true;
    this.startTime = Date.now();

    this.timerInterval = setInterval(() => {
      this.elapsedSec++;
      if (this.mode === 'countdown') {
        if (this.remainingSec > 0) {
          this.remainingSec--;
        } else {
          this._handleTimerExpired();
        }
      }
      this._updateDisplay();
    }, 1000);

    const btnToggle = this.container.querySelector('#btn-timer-toggle');
    if (btnToggle) btnToggle.textContent = 'Pause';
  }

  /**
   * Pauses the active timer.
   * @agent eln-frontend-agent
   * @role Timer Pause Controller
   * @returns {void}
   */
  pause() {
    if (!this.isRunning) return;
    this.isRunning = false;
    clearInterval(this.timerInterval);
    this.timerInterval = null;

    const btnToggle = this.container.querySelector('#btn-timer-toggle');
    if (btnToggle) btnToggle.textContent = 'Resume';
  }

  /**
   * Resets timer back to initial configured target state.
   * @agent eln-frontend-agent
   * @role Timer Reset Controller
   * @returns {void}
   */
  reset() {
    this.pause();
    this.remainingSec = this.targetDurationSec;
    this.elapsedSec = 0;
    this._updateDisplay();

    const btnToggle = this.container.querySelector('#btn-timer-toggle');
    if (btnToggle) btnToggle.textContent = 'Start Timer';
  }

  /**
   * Sets a preset duration and label.
   * @agent eln-frontend-agent
   * @role Preset Controller
   * @param {number} sec - Duration in seconds
   * @param {string} stepName - Description label
   * @returns {void}
   */
  setPreset(sec, stepName) {
    this.pause();
    this.targetDurationSec = sec;
    this.remainingSec = sec;
    this.elapsedSec = 0;
    this.options.stepName = stepName;
    this.render();
  }

  /**
   * Updates the clock digital digits without redrawing the whole component.
   * @agent eln-frontend-agent
   * @role High-Performance Display Update
   * @private
   * @returns {void}
   */
  _updateDisplay() {
    const clockEl = this.container.querySelector('#timer-clock-digits');
    if (clockEl) {
      clockEl.textContent = this._formatTime(this.mode === 'countdown' ? this.remainingSec : this.elapsedSec);
    }
  }

  /**
   * Formats total seconds into HH:MM:SS or MM:SS string.
   * @agent eln-frontend-agent
   * @role Time Formatter Helper
   * @private
   * @param {number} totalSec - Total seconds
   * @returns {string} Formatted string
   */
  _formatTime(totalSec) {
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;

    const pad = (v) => String(v).padStart(2, '0');
    if (h > 0) {
      return `${pad(h)}:${pad(m)}:${pad(s)}`;
    }
    return `${pad(m)}:${pad(s)}`;
  }

  /**
   * Handles timer expiry alert and visual glow.
   * @agent eln-frontend-agent
   * @role Alert Handler
   * @private
   * @returns {void}
   */
  _handleTimerExpired() {
    this.pause();
    this._playBeepAlert();

    const clockEl = this.container.querySelector('#timer-clock-digits');
    if (clockEl) {
      clockEl.style.color = 'var(--fail)';
      clockEl.classList.add('pulse-alert');
    }

    if (typeof this.options.onTimerExpired === 'function') {
      this.options.onTimerExpired(this.options.stepName);
    }
  }

  /**
   * Generates a synthetic acoustic alert chime using Web Audio API.
   * @agent eln-frontend-agent
   * @role Audio Synthesizer
   * @private
   * @returns {void}
   */
  _playBeepAlert() {
    try {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtxClass) return;
      if (!this.audioCtx) this.audioCtx = new AudioCtxClass();

      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, this.audioCtx.currentTime); // A5 note
      osc.frequency.exponentialRampToValueAtTime(440, this.audioCtx.currentTime + 0.4);

      gain.gain.setValueAtTime(0.15, this.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.4);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start();
      osc.stop(this.audioCtx.currentTime + 0.4);
    } catch {
      // Audio autoplay policy fallback
    }
  }

  /**
   * Records a formal kinetic timepoint entry and computes SOP target deviation.
   * @agent eln-frontend-agent
   * @role SOP Compliance & Kinetic Timepoint Logger
   * @param {string} label - Step description
   * @param {string} paramName - Name of tracked variable (e.g., 'OD600')
   * @param {number} paramValue - Value of tracked variable
   * @returns {KineticTimepoint} Stamped timepoint record
   */
  stampTimepoint(label, paramName = 'OD600', paramValue = 0.0) {
    const actualSec = this.elapsedSec;
    const targetSec = this.targetDurationSec;
    const deviationSec = actualSec - targetSec;

    let deviationBadge = '00:00';
    let deviationStatus = 'PASS';

    const absDev = Math.abs(deviationSec);
    const mm = String(Math.floor(absDev / 60)).padStart(2, '0');
    const ss = String(absDev % 60).padStart(2, '0');

    if (deviationSec > 0) {
      deviationBadge = `+${mm}:${ss}`;
      deviationStatus = deviationSec > 300 ? 'FLAG' : 'PASS'; // Flag if > 5m late
    } else if (deviationSec < 0) {
      deviationBadge = `-${mm}:${ss}`;
      deviationStatus = absDev > 300 ? 'EARLY' : 'PASS';
    }

    const timepoint = {
      id: `TP-${Date.now().toString(36).toUpperCase()}`,
      label: label || this.options.stepName,
      timestampIso: new Date().toISOString(),
      targetDurationSec: targetSec,
      actualDurationSec: actualSec,
      deviationSec,
      deviationBadge,
      deviationStatus,
      paramName,
      paramValue,
      operator: 'Active Researcher'
    };

    this.timepoints.push(timepoint);

    if (typeof this.options.onTimepointStamped === 'function') {
      this.options.onTimepointStamped(timepoint);
    }

    return timepoint;
  }
}
