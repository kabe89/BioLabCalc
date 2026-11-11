/**
 * @file ocr_corrector.js
 * @agent eln-frontend-agent
 * @description Interactive Human-in-the-Loop (HITL) OCR Review, Tag Parser & Error Corrector.
 * @architecture Parses synthetic or real OCR digitized notebook entries containing embedded uncertainty tags:
 *               `[[UNCERTAIN:id="..." text="..." conf=0.xx bbox="[x,y,w,h]" candidates="[...]"]]`
 *               Renders interactive amber highlight pills, manages popover source snippet crops,
 *               candidate chip selection, inline edits, and verification signatures.
 */

/**
 * Represents an uncertain OCR token identified by the ML pipeline.
 * @typedef {Object} UncertainToken
 * @property {string} id - Unique tag ID
 * @property {string} text - Digitized token text
 * @property {number} conf - Model confidence score (0.0 to 1.0)
 * @property {Array<number>} bbox - Bounding box [x, y, width, height]
 * @property {Array<string>} candidates - Top OCR alternative predictions
 * @property {boolean} resolved - Whether user has accepted or corrected the token
 * @property {string} [resolvedText] - The accepted text value
 */

/**
 * OCRCorrector Class: Drives the HITL text rendering, interactive popover, and correction loop.
 * @agent eln-frontend-agent
 * @role HITL OCR interactive reviewer component
 */
export class OCRCorrector {
  /**
   * Initializes the OCRCorrector instance.
   * @agent eln-frontend-agent
   * @role Component Constructor
   * @param {string|HTMLElement} textContainer - Container element for transcription text
   * @param {Object} options - Configuration options
   * @param {string} [options.rawText] - Initial raw text with UNCERTAIN tags
   * @param {Function} [options.onTokenResolved] - Callback when an uncertain token is corrected
   * @param {Function} [options.onAllResolved] - Callback when all uncertain tokens are verified
   */
  constructor(textContainer, options = {}) {
    this.container = typeof textContainer === 'string' ? document.getElementById(textContainer) : textContainer;
    if (!this.container) {
      throw new Error(`[OCRCorrector] Container element not found: ${textContainer}`);
    }

    this.options = Object.assign({
      rawText: '',
      onTokenResolved: null,
      onAllResolved: null
    }, options);

    // Parsed Tokens Registry
    this.tokens = new Map();
    this.activePopoverEl = null;

    if (this.options.rawText) {
      this.loadText(this.options.rawText);
    }
  }

  /**
   * Parses raw string with embedded tags and renders interactive markup.
   * @agent eln-frontend-agent
   * @role Tag Parser & Markup Engine
   * @param {string} rawText - Text containing [[UNCERTAIN:...]] tags
   * @returns {void}
   */
  loadText(rawText) {
    this.tokens.clear();
    this._closeActivePopover();

    // Regex pattern matching [[UNCERTAIN:id="..." text="..." conf=... bbox="..." candidates="..."]]
    const pattern = /\[\[UNCERTAIN:\s*id="([^"]+)"\s*text="([^"]+)"\s*conf=([\d\.]+)\s*bbox="([^"]+)"\s*candidates="([^"]+)"\s*\]\]/g;

    let html = '';
    let lastIndex = 0;
    let match;

    while ((match = pattern.exec(rawText)) !== null) {
      const matchIndex = match.index;
      // Append preceding safe text
      html += this._escapeHtml(rawText.substring(lastIndex, matchIndex));

      const id = match[1];
      const text = match[2];
      const conf = parseFloat(match[3]);
      const bboxStr = match[4];
      const candStr = match[5];

      let bbox = [100, 100, 120, 30];
      try {
        bbox = JSON.parse(bboxStr);
      } catch {
        // Fallback bounding box
      }

      let candidates = [text];
      try {
        candidates = JSON.parse(candStr.replace(/'/g, '"'));
      } catch {
        // Fallback candidates
      }

      const token = {
        id,
        text,
        conf,
        bbox,
        candidates,
        resolved: false,
        resolvedText: text
      };
      this.tokens.set(id, token);

      const confPct = Math.round(conf * 100);
      html += `<span class="uncertain-tag-pill" data-token-id="${id}" title="Click to review OCR transcription">
        <span class="token-val">${this._escapeHtml(text)}</span>
        <span class="uncertain-conf-badge">${confPct}%</span>
      </span>`;

      lastIndex = pattern.lastIndex;
    }

    // Append remainder
    html += this._escapeHtml(rawText.substring(lastIndex));
    this.container.innerHTML = html;

    this._bindTagInteractions();
  }

  /**
   * Binds click events to uncertain word pills.
   * @agent eln-frontend-agent
   * @role Interactive DOM Binding
   * @private
   * @returns {void}
   */
  _bindTagInteractions() {
    const pills = this.container.querySelectorAll('.uncertain-tag-pill');
    pills.forEach((pill) => {
      pill.addEventListener('click', (e) => {
        e.stopPropagation();
        const tokenId = pill.dataset.tokenId;
        const token = this.tokens.get(tokenId);
        if (token) {
          this._openPopover(pill, token);
        }
      });
    });

    // Close popover when clicking anywhere else
    document.addEventListener('click', (e) => {
      if (this.activePopoverEl && !this.activePopoverEl.contains(e.target)) {
        this._closeActivePopover();
      }
    });
  }

  /**
   * Opens the interactive HITL review popover anchored to the target pill.
   * @agent eln-frontend-agent
   * @role Popover Coordinator
   * @private
   * @param {HTMLElement} pillEl - Anchored pill DOM element
   * @param {UncertainToken} token - Token data object
   * @returns {void}
   */
  _openPopover(pillEl, token) {
    this._closeActivePopover();

    const popover = document.createElement('div');
    popover.className = 'ocr-interactive-popover';

    const confPct = Math.round(token.conf * 100);

    popover.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <span style="font-size:0.75rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">
          HITL OCR Validation
        </span>
        <span class="badge ${confPct >= 80 ? 'badge-pass' : 'badge-flag'}">${confPct}% Conf</span>
      </div>

      <!-- Simulated Bounding Box Source Snippet -->
      <div class="ocr-crop-snippet-box">
        <div style="font-family:'Courier New', monospace; font-size:1.1rem; font-weight:700; color:#38bdf8; letter-spacing:1px; background:#020617; padding:4px 12px; border-radius:4px; border:1px solid #1e293b;">
          ${token.text}
        </div>
      </div>

      <div style="font-size:0.75rem; color:var(--text-muted); margin-bottom:6px;">Suggested Candidates:</div>
      <div class="ocr-candidate-chips-row">
        ${token.candidates.map((cand) => `<button class="ocr-candidate-chip" data-cand="${this._escapeHtml(cand)}">${this._escapeHtml(cand)}</button>`).join('')}
      </div>

      <div style="margin-top:12px;">
        <label style="font-size:0.75rem; color:var(--text-muted); display:block; margin-bottom:4px;">Confirmed Value:</label>
        <input type="text" id="ocr-edit-input" value="${this._escapeHtml(token.resolvedText || token.text)}" style="width:100%; padding:6px 10px; font-size:0.85rem; border:1px solid var(--border); border-radius:4px; font-family:var(--font-mono); margin-bottom:12px;">
      </div>

      <div style="display:flex; gap:8px;">
        <button class="btn btn-primary btn-sm" id="btn-accept-ocr" style="flex:1;">
          Accept & Confirm
        </button>
        <button class="btn btn-outline btn-sm" id="btn-flag-rescan">
          Flag Re-scan
        </button>
      </div>
    `;

    document.body.appendChild(popover);
    this.activePopoverEl = popover;

    // Position popover right below the pill
    const pillRect = pillEl.getBoundingClientRect();
    let top = pillRect.bottom + window.scrollY + 6;
    let left = pillRect.left + window.scrollX - 20;

    if (left + 330 > window.innerWidth) {
      left = window.innerWidth - 340;
    }
    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;

    // Candidate chip selection
    const chips = popover.querySelectorAll('.ocr-candidate-chip');
    chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        const input = popover.querySelector('#ocr-edit-input');
        if (input) input.value = chip.dataset.cand;
      });
    });

    // Accept action
    const btnAccept = popover.querySelector('#btn-accept-ocr');
    if (btnAccept) {
      btnAccept.addEventListener('click', () => {
        const input = popover.querySelector('#ocr-edit-input');
        const confirmedVal = input ? input.value.trim() : token.text;
        this.resolveToken(token.id, confirmedVal);
        this._closeActivePopover();
      });
    }

    // Flag for re-scan action
    const btnFlag = popover.querySelector('#btn-flag-rescan');
    if (btnFlag) {
      btnFlag.addEventListener('click', () => {
        pillEl.style.borderColor = 'var(--fail)';
        pillEl.style.backgroundColor = 'var(--fail-bg)';
        this._closeActivePopover();
      });
    }
  }

  /**
   * Closes the active popover if currently open.
   * @agent eln-frontend-agent
   * @role Popover Cleanup
   * @private
   * @returns {void}
   */
  _closeActivePopover() {
    if (this.activePopoverEl && this.activePopoverEl.parentNode) {
      this.activePopoverEl.parentNode.removeChild(this.activePopoverEl);
      this.activePopoverEl = null;
    }
  }

  /**
   * Resolves an uncertain token with the user's accepted or edited value.
   * @agent eln-frontend-agent
   * @role Token Resolution Engine
   * @param {string} tokenId - Tag identifier
   * @param {string} resolvedValue - User verified text
   * @returns {void}
   */
  resolveToken(tokenId, resolvedValue) {
    const token = this.tokens.get(tokenId);
    if (!token) return;

    token.resolved = true;
    token.resolvedText = resolvedValue;

    // Update pill DOM element
    const pillEl = this.container.querySelector(`.uncertain-tag-pill[data-token-id="${tokenId}"]`);
    if (pillEl) {
      pillEl.style.borderColor = 'var(--pass)';
      pillEl.style.backgroundColor = 'var(--pass-bg)';
      pillEl.style.color = 'var(--pass)';

      const valEl = pillEl.querySelector('.token-val');
      if (valEl) valEl.textContent = resolvedValue;

      const badgeEl = pillEl.querySelector('.uncertain-conf-badge');
      if (badgeEl) {
        badgeEl.textContent = 'VERIFIED';
        badgeEl.style.backgroundColor = 'var(--pass)';
      }
    }

    if (typeof this.options.onTokenResolved === 'function') {
      this.options.onTokenResolved(token);
    }

    // Check if all tokens are resolved
    let allDone = true;
    for (const t of this.tokens.values()) {
      if (!t.resolved) {
        allDone = false;
        break;
      }
    }

    if (allDone && typeof this.options.onAllResolved === 'function') {
      this.options.onAllResolved(this.getFinalCleanText());
    }
  }

  /**
   * Produces clean plain-text output with all uncertain tags replaced by verified text.
   * @agent eln-frontend-agent
   * @role Clean Output Serializer
   * @returns {string} Sanitized verified text
   */
  getFinalCleanText() {
    // Clone container text node content
    let clean = this.container.innerText;
    return clean;
  }

  /**
   * Escapes HTML entities for security against XSS.
   * @agent eln-frontend-agent
   * @role HTML Sanitizer
   * @private
   * @param {string} str - Raw input
   * @returns {string} Escaped string
   */
  _escapeHtml(str) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return str.replace(/[&<>"']/g, (m) => map[m]);
  }
}
