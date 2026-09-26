"""Interactive Drag-and-Drop Gel Annotator and Molecular Weight Calculator."""

from __future__ import annotations
import http.server
import math
import os
import socketserver
import threading
import webbrowser
from typing import Dict, List, Optional, Tuple

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BioLabCalc | Interactive Drag & Drop Gel Annotator</title>
  <style>
    :root {
      --primary: #1F4E79;
      --primary-hover: #163857;
      --accent: #2563EB;
      --bg: #F8FAFC;
      --surface: #FFFFFF;
      --border: #E2E8F0;
      --text: #0F172A;
      --text-muted: #64748B;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    header {
      background: var(--primary);
      color: white;
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    header h1 { font-size: 1.15rem; font-weight: 700; display: flex; align-items: center; gap: 8px; }
    .badge { background: #3B82F6; padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
    .toolbar-actions { display: flex; gap: 10px; }
    button {
      background: var(--surface);
      color: var(--primary);
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    button:hover { background: #F1F5F9; border-color: #CBD5E1; }
    button.primary { background: #2563EB; color: white; border: none; }
    button.primary:hover { background: #1D4ED8; }
    .main-container {
      display: flex;
      flex: 1;
      height: calc(100vh - 54px);
      overflow: hidden;
    }
    .sidebar {
      width: 340px;
      background: var(--surface);
      border-right: 1px solid var(--border);
      overflow-y: auto;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .panel-section {
      background: #F8FAFC;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
    }
    .panel-section h3 {
      font-size: 0.88rem;
      font-weight: 700;
      color: var(--primary);
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .form-group { margin-bottom: 10px; }
    .form-group:last-child { margin-bottom: 0; }
    label { display: block; font-size: 0.78rem; font-weight: 600; color: var(--text-muted); margin-bottom: 4px; }
    input[type="text"], input[type="number"], select {
      width: 100%;
      padding: 6px 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.85rem;
      background: white;
    }
    .slider-row { display: flex; align-items: center; gap: 8px; }
    .slider-row input[type="range"] { flex: 1; }
    .slider-row span { font-size: 0.8rem; font-weight: 600; width: 36px; text-align: right; }
    .drop-zone {
      border: 2px dashed #94A3B8;
      border-radius: 8px;
      padding: 16px;
      text-align: center;
      cursor: pointer;
      background: #F1F5F9;
      transition: background 0.15s;
    }
    .drop-zone:hover, .drop-zone.dragover { background: #E2E8F0; border-color: var(--accent); }
    .drop-zone p { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }
    .canvas-container {
      flex: 1;
      background: #0F172A;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      overflow: auto;
      padding: 20px;
    }
    #gelCanvas {
      background: #1E293B;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      border-radius: 6px;
      cursor: crosshair;
    }
    .lane-list {
      max-height: 140px;
      overflow-y: auto;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: white;
    }
    .lane-item {
      padding: 6px 10px;
      font-size: 0.8rem;
      display: flex;
      justify-content: space-between;
      border-bottom: 1px solid #F1F5F9;
    }
    .lane-item:last-child { border-bottom: none; }
    .info-callout {
      background: #EFF6FF;
      border-left: 3px solid #3B82F6;
      padding: 8px 12px;
      font-size: 0.78rem;
      color: #1E40AF;
      border-radius: 0 4px 4px 0;
      line-height: 1.4;
    }
    .mw-calc-result {
      background: #ECFDF5;
      border: 1px solid #A7F3D0;
      border-radius: 6px;
      padding: 10px;
      margin-top: 8px;
    }
    .mw-val { font-size: 1.2rem; font-weight: 700; color: #065F46; }
  </style>
</head>
<body>
  <header>
    <h1>🧬 BioLabCalc <span>Gel Annotator</span> <span class="badge">Drag & Drop</span></h1>
    <div class="toolbar-actions">
      <button onclick="loadDemoGel()">🧪 Load Demo Gel</button>
      <button onclick="invertGelColors()">🌓 Invert B/W</button>
      <button onclick="clearAnnotations()">🗑️ Clear Bands</button>
      <button class="primary" onclick="exportGelPNG()">💾 Export PNG</button>
      <button onclick="exportTableCSV()">📊 Export CSV</button>
    </div>
  </header>

  <div class="main-container">
    <div class="sidebar">
      <!-- 1. Image Upload & Display Controls -->
      <div class="panel-section">
        <h3>1. Gel Image <span style="font-size:0.75rem; color:#64748B;">Drag & Drop</span></h3>
        <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
          <span style="font-size:1.5rem;">📥</span>
          <p>Drop Gel Image Here or Click to Browse</p>
          <input type="file" id="fileInput" accept="image/*" style="display:none;" onchange="handleFileSelect(event)">
        </div>
        <div class="form-group" style="margin-top: 10px;">
          <label>Contrast</label>
          <div class="slider-row">
            <input type="range" id="contrastRange" min="50" max="250" value="100" oninput="updateImageFilters()">
            <span id="contrastVal">100%</span>
          </div>
        </div>
        <div class="form-group">
          <label>Brightness</label>
          <div class="slider-row">
            <input type="range" id="brightnessRange" min="50" max="200" value="100" oninput="updateImageFilters()">
            <span id="brightnessVal">100%</span>
          </div>
        </div>
      </div>

      <!-- 2. Lane Configuration -->
      <div class="panel-section">
        <h3>2. Lanes & Samples</h3>
        <div class="form-group">
          <label>Number of Lanes</label>
          <input type="number" id="numLanesInput" min="2" max="24" value="6" onchange="initLanes(this.value)">
        </div>
        <div class="form-group">
          <label>Lane Setup (Click to edit names)</label>
          <div class="lane-list" id="laneList"></div>
        </div>
      </div>

      <!-- 3. Molecular Weight Ladder Calibration -->
      <div class="panel-section">
        <h3>3. Ladder Calibration</h3>
        <div class="form-group">
          <label>Ladder Type</label>
          <select id="ladderSelect" onchange="changeLadderType(this.value)">
            <option value="1kb_dna">1 kb DNA Ladder (500 bp - 10 kb)</option>
            <option value="100bp_dna">100 bp DNA Ladder (100 bp - 1.5 kb)</option>
            <option value="protein_broad_range">Prestained Protein Ladder (10 - 250 kDa)</option>
            <option value="low_range_ssdna">Low-Range Oligo Ladder (10 - 100 nt)</option>
          </select>
        </div>
        <div class="form-group">
          <label>Ladder Lane</label>
          <select id="ladderLaneSelect" onchange="setLadderLane(this.value)"></select>
        </div>
        <div class="info-callout">
          <strong>How to calculate MW:</strong> Click anywhere on a sample lane to pick a band. The tool computes relative mobility (Rf) and calculates molecular weight using the logarithmic standard curve fit.
        </div>
      </div>

      <!-- 4. Selected Band Readout -->
      <div class="panel-section">
        <h3>4. Band Readout & Picked Bands</h3>
        <div id="bandReadout" class="mw-calc-result" style="display:none;">
          <div style="font-size:0.75rem; color:#047857; font-weight:600;">INTERPOLATED MOLECULAR WEIGHT:</div>
          <div class="mw-val" id="pickedMwText">--</div>
          <div style="font-size:0.78rem; color:#065F46; margin-top:2px;" id="pickedRfText">Rf: --</div>
        </div>
        <div style="margin-top: 10px; font-size:0.75rem; color:#64748B;">
          Double-click any label on the gel to edit text or delete. Drag tags to reposition callouts.
        </div>
      </div>
    </div>

    <!-- Interactive Gel Canvas -->
    <div class="canvas-container">
      <canvas id="gelCanvas" width="850" height="680"></canvas>
    </div>
  </div>

  <script>
    const LADDERS = {
      "1kb_dna": {
        name: "1 kb DNA Ladder", unit: "bp",
        bands: [10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 500],
        refs: [3000]
      },
      "100bp_dna": {
        name: "100 bp DNA Ladder", unit: "bp",
        bands: [1517, 1200, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 100],
        refs: [500, 1000]
      },
      "protein_broad_range": {
        name: "Protein Prestained Ladder", unit: "kDa",
        bands: [250, 150, 100, 75, 50, 37, 25, 20, 15, 10],
        refs: [75, 25]
      },
      "low_range_ssdna": {
        name: "Low-Range ssDNA Oligo Ladder", unit: "nt",
        bands: [100, 80, 60, 50, 40, 30, 20, 10],
        refs: [50]
      }
    };

    let canvas = document.getElementById("gelCanvas");
    let ctx = canvas.getContext("2d");
    let gelImg = null;
    let inverted = true;
    let lanes = ["1 kb Ladder", "Neg Ctrl", "Clone 1", "Clone 2", "Clone 3", "Digest"];
    let ladderLane = 1;
    let ladderType = "1kb_dna";
    let bands = [];
    let draggingBand = null;
    let dragOffsetX = 0, dragOffsetY = 0;

    // Standard curve parameters (Rf vs log10(MW))
    let calibSlope = -1.25;
    let calibIntercept = 4.15;

    function init() {
      setupDropZone();
      initLanes(6);
      loadDemoGel();
      setupCanvasEvents();
    }

    function setupDropZone() {
      let dz = document.getElementById("dropZone");
      dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
      dz.addEventListener("dragleave", () => { dz.classList.remove("dragover"); });
      dz.addEventListener("drop", (e) => {
        e.preventDefault();
        dz.classList.remove("dragover");
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          loadImageFile(e.dataTransfer.files[0]);
        }
      });
    }

    function handleFileSelect(e) {
      if (e.target.files && e.target.files[0]) {
        loadImageFile(e.target.files[0]);
      }
    }

    function loadImageFile(file) {
      let reader = new FileReader();
      reader.onload = (evt) => {
        let img = new Image();
        img.onload = () => {
          gelImg = img;
          canvas.width = Math.max(850, img.width);
          canvas.height = Math.max(680, img.height);
          render();
        };
        img.src = evt.target.result;
      };
      reader.readAsDataURL(file);
    }

    function loadDemoGel() {
      // Create synthetic gel background image
      let w = 850, h = 680;
      canvas.width = w;
      canvas.height = h;
      gelImg = null;
      bands = [
        { lane: 3, y: 395, mw: 850, label: "850 bp Target", color: "#F59E0B", calloutX: 0, calloutY: -20 },
        { lane: 5, y: 395, mw: 850, label: "850 bp Target", color: "#F59E0B", calloutX: 0, calloutY: -20 },
        { lane: 6, y: 235, mw: 3200, label: "3.2 kb Vector", color: "#2563EB", calloutX: 0, calloutY: -20 }
      ];
      render();
    }

    function initLanes(num) {
      num = parseInt(num) || 6;
      let newLanes = [];
      for (let i = 0; i < num; i++) {
        newLanes.push(lanes[i] || (i === 0 ? "Ladder" : `Sample ${i}`));
      }
      lanes = newLanes;
      updateLaneUI();
      render();
    }

    function updateLaneUI() {
      let list = document.getElementById("laneList");
      let sel = document.getElementById("ladderLaneSelect");
      list.innerHTML = "";
      sel.innerHTML = "";

      lanes.forEach((name, idx) => {
        let lNum = idx + 1;
        let item = document.createElement("div");
        item.className = "lane-item";
        item.innerHTML = `<span><strong>L${lNum}:</strong> ${name}</span><button style="padding:2px 6px; font-size:0.7rem;" onclick="renameLane(${idx})">Edit</button>`;
        list.appendChild(item);

        let opt = document.createElement("option");
        opt.value = lNum;
        opt.textContent = `Lane ${lNum} (${name})`;
        if (lNum === ladderLane) opt.selected = true;
        sel.appendChild(opt);
      });
    }

    function renameLane(idx) {
      let cur = lanes[idx];
      let res = prompt(`Rename Lane ${idx+1}:`, cur);
      if (res !== null && res.trim() !== "") {
        lanes[idx] = res.trim();
        updateLaneUI();
        render();
      }
    }

    function setLadderLane(val) {
      ladderLane = parseInt(val);
      render();
    }

    function changeLadderType(val) {
      ladderType = val;
      render();
    }

    function invertGelColors() {
      inverted = !inverted;
      render();
    }

    function clearAnnotations() {
      bands = [];
      document.getElementById("bandReadout").style.display = "none";
      render();
    }

    function updateImageFilters() {
      document.getElementById("contrastVal").textContent = document.getElementById("contrastRange").value + "%";
      document.getElementById("brightnessVal").textContent = document.getElementById("brightnessRange").value + "%";
      render();
    }

    function calculateRf(y, topY, bottomY) {
      return Math.max(0.01, Math.min(0.99, (y - topY) / (bottomY - topY)));
    }

    function interpolateMwFromRf(rf) {
      // log10(MW) = intercept + slope * Rf
      let ladder = LADDERS[ladderType];
      let maxMw = Math.max(...ladder.bands);
      let minMw = Math.min(...ladder.bands);
      let logMax = Math.log10(maxMw);
      let logMin = Math.log10(minMw);

      // Log-linear interpolation
      let logVal = logMax - rf * (logMax - logMin);
      let estMw = Math.pow(10, logVal);

      if (ladder.unit === "bp") {
        return Math.round(estMw / 10) * 10;
      } else {
        return Math.round(estMw * 10) / 10;
      }
    }

    function render() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      let contrast = document.getElementById("contrastRange").value;
      let brightness = document.getElementById("brightnessRange").value;
      ctx.filter = `contrast(${contrast}%) brightness(${brightness}%)`;

      let gelX = 80, gelY = 70;
      let gelW = canvas.width - 150;
      let gelH = canvas.height - 110;

      if (gelImg) {
        ctx.save();
        if (inverted) {
          ctx.filter += " invert(100%)";
        }
        ctx.drawImage(gelImg, gelX, gelY, gelW, gelH);
        ctx.restore();
      } else {
        // Draw synthetic gel
        ctx.fillStyle = inverted ? "#F1F5F9" : "#0F172A";
        ctx.fillRect(gelX, gelY, gelW, gelH);

        // Wells
        let laneW = gelW / lanes.length;
        for (let i = 0; i < lanes.length; i++) {
          let lx = gelX + i * laneW + laneW * 0.2;
          ctx.fillStyle = inverted ? "#CBD5E1" : "#1E293B";
          ctx.fillRect(lx, gelY + 10, laneW * 0.6, 18);
        }

        // Ladder bands
        let lad = LADDERS[ladderType];
        let ladX = gelX + (ladderLane - 1) * laneW + laneW * 0.15;
        let bandW = laneW * 0.7;

        lad.bands.forEach(b => {
          let rf = calculateRfForSize(b, lad);
          let by = gelY + 40 + rf * (gelH - 80);
          let isRef = lad.refs.includes(b);

          ctx.fillStyle = inverted ? (isRef ? "rgba(15,23,42,0.95)" : "rgba(30,41,59,0.75)")
                                   : (isRef ? "rgba(248,250,252,0.95)" : "rgba(226,232,240,0.75)");
          ctx.beginPath();
          ctx.roundRect(ladX, by - 3, bandW, isRef ? 7 : 4, [2]);
          ctx.fill();
        });

        // Synthetic sample bands
        bands.forEach(b => {
          if (b.lane !== ladderLane) {
            let sx = gelX + (b.lane - 1) * laneW + laneW * 0.15;
            ctx.fillStyle = inverted ? "rgba(15,23,42,0.85)" : "rgba(241,245,249,0.85)";
            ctx.beginPath();
            ctx.roundRect(sx, b.y - 3, bandW, 5, [2]);
            ctx.fill();
          }
        });
      }

      ctx.filter = "none";

      // Draw Lane Numbers and Headers
      let laneW = gelW / lanes.length;
      ctx.textAlign = "center";
      for (let i = 0; i < lanes.length; i++) {
        let lx = gelX + (i + 0.5) * laneW;

        // Lane number circle
        ctx.fillStyle = "#1F4E79";
        ctx.beginPath();
        ctx.arc(lx, gelY - 32, 11, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#FFFFFF";
        ctx.font = "bold 11px sans-serif";
        ctx.fillText(i + 1, lx, gelY - 28);

        // Lane name rotated
        ctx.save();
        ctx.translate(lx, gelY - 14);
        ctx.fillStyle = inverted ? "#0F172A" : "#F8FAFC";
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(lanes[i], 0, 0);
        ctx.restore();

        // Lane separator line
        ctx.strokeStyle = "rgba(148,163,184,0.25)";
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(gelX + i * laneW, gelY);
        ctx.lineTo(gelX + i * laneW, gelY + gelH);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Draw Ladder Molecular Weight Labels
      let lad = LADDERS[ladderType];
      lad.bands.forEach(b => {
        let rf = calculateRfForSize(b, lad);
        let by = gelY + 40 + rf * (gelH - 80);
        let isRef = lad.refs.includes(b);

        let lbl = b >= 1000 && lad.unit === "bp" ? (b/1000).toFixed(1).replace(".0","") + " kb" : b + " " + lad.unit;
        if (isRef) lbl += " *";

        ctx.fillStyle = isRef ? "#2563EB" : (inverted ? "#475569" : "#94A3B8");
        ctx.font = isRef ? "bold 11px sans-serif" : "10px sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(lbl, gelX - 10, by + 3);

        ctx.strokeStyle = "rgba(148,163,184,0.4)";
        ctx.beginPath();
        ctx.moveTo(gelX - 6, by);
        ctx.lineTo(gelX, by);
        ctx.stroke();
      });

      // Draw Annotated Sample Bands
      bands.forEach((b, idx) => {
        let sx = gelX + (b.lane - 0.5) * laneW;
        let tagX = sx + (b.calloutX || 25);
        let tagY = b.y + (b.calloutY || -15);

        // Arrow from tag to band
        ctx.strokeStyle = b.color || "#F59E0B";
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(tagX, tagY);
        ctx.lineTo(sx, b.y);
        ctx.stroke();

        // Tag Pill
        ctx.font = "bold 11px sans-serif";
        let txt = `${b.label} (${b.mw} ${lad.unit})`;
        let tw = ctx.measureText(txt).width;

        ctx.fillStyle = "#FEF3C7";
        ctx.strokeStyle = "#D97706";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.roundRect(tagX - 6, tagY - 14, tw + 12, 20, [4]);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#92400E";
        ctx.textAlign = "left";
        ctx.fillText(txt, tagX, tagY);
      });
    }

    function calculateRfForSize(size, ladder) {
      let maxMw = Math.max(...ladder.bands);
      let minMw = Math.min(...ladder.bands);
      let logMax = Math.log10(maxMw);
      let logMin = Math.log10(minMw);
      let logVal = Math.log10(size);
      return Math.max(0.02, Math.min(0.98, (logMax - logVal) / (logMax - logMin)));
    }

    function setupCanvasEvents() {
      canvas.addEventListener("mousedown", (e) => {
        let rect = canvas.getBoundingClientRect();
        let mouseX = e.clientX - rect.left;
        let mouseY = e.clientY - rect.top;

        // Check if clicking near an existing band tag
        for (let b of bands) {
          let gelX = 80, gelW = canvas.width - 150;
          let laneW = gelW / lanes.length;
          let sx = gelX + (b.lane - 0.5) * laneW;
          let tagX = sx + (b.calloutX || 25);
          let tagY = b.y + (b.calloutY || -15);

          if (Math.abs(mouseX - tagX) < 40 && Math.abs(mouseY - tagY) < 15) {
            draggingBand = b;
            dragOffsetX = mouseX - tagX;
            dragOffsetY = mouseY - tagY;
            return;
          }
        }

        // Otherwise: Pick new band at click position
        let gelX = 80, gelY = 70;
        let gelW = canvas.width - 150;
        let gelH = canvas.height - 110;

        if (mouseX >= gelX && mouseX <= gelX + gelW && mouseY >= gelY + 30 && mouseY <= gelY + gelH) {
          let laneW = gelW / lanes.length;
          let laneIdx = Math.floor((mouseX - gelX) / laneW) + 1;
          let rf = calculateRf(mouseY, gelY + 40, gelY + gelH - 40);
          let estMw = interpolateMwFromRf(rf);

          let lad = LADDERS[ladderType];
          document.getElementById("bandReadout").style.display = "block";
          document.getElementById("pickedMwText").textContent = `${estMw} ${lad.unit}`;
          document.getElementById("pickedRfText").textContent = `Relative Mobility (Rf): ${rf.toFixed(3)} | Lane ${laneIdx} (${lanes[laneIdx-1]})`;

          if (laneIdx !== ladderLane) {
            bands.push({
              lane: laneIdx,
              y: mouseY,
              mw: estMw,
              label: `Band`,
              color: "#F59E0B",
              calloutX: 20,
              calloutY: -20
            });
            render();
          }
        }
      });

      canvas.addEventListener("mousemove", (e) => {
        if (draggingBand) {
          let rect = canvas.getBoundingClientRect();
          let mouseX = e.clientX - rect.left;
          let mouseY = e.clientY - rect.top;
          let gelX = 80, gelW = canvas.width - 150;
          let laneW = gelW / lanes.length;
          let sx = gelX + (draggingBand.lane - 0.5) * laneW;

          draggingBand.calloutX = mouseX - sx - dragOffsetX;
          draggingBand.calloutY = mouseY - draggingBand.y - dragOffsetY;
          render();
        }
      });

      canvas.addEventListener("mouseup", () => { draggingBand = null; });
      canvas.addEventListener("mouseleave", () => { draggingBand = null; });

      canvas.addEventListener("dblclick", (e) => {
        let rect = canvas.getBoundingClientRect();
        let mouseX = e.clientX - rect.left;
        let mouseY = e.clientY - rect.top;

        for (let i = 0; i < bands.length; i++) {
          let b = bands[i];
          let gelX = 80, gelW = canvas.width - 150;
          let laneW = gelW / lanes.length;
          let sx = gelX + (b.lane - 0.5) * laneW;
          let tagX = sx + (b.calloutX || 25);
          let tagY = b.y + (b.calloutY || -15);

          if (Math.abs(mouseX - tagX) < 40 && Math.abs(mouseY - tagY) < 15) {
            let choice = prompt(`Edit label for band (${b.mw} ${LADDERS[ladderType].unit}) [type 'DELETE' to remove]:`, b.label);
            if (choice === "DELETE") {
              bands.splice(i, 1);
            } else if (choice !== null) {
              b.label = choice.trim();
            }
            render();
            return;
          }
        }
      });
    }

    function exportGelPNG() {
      let link = document.createElement("a");
      link.download = "annotated_gel_figure.png";
      link.href = canvas.toDataURL("image/png");
      link.click();
    }

    function exportTableCSV() {
      let lad = LADDERS[ladderType];
      let rows = [["Lane_Number", "Lane_Name", "Band_Size_" + lad.unit, "Label", "Relative_Mobility_Rf"]];
      bands.forEach(b => {
        let gelY = 70, gelH = canvas.height - 110;
        let rf = calculateRf(b.y, gelY + 40, gelY + gelH - 40);
        rows.push([b.lane, lanes[b.lane - 1], b.mw, b.label, rf.toFixed(3)]);
      });
      let csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");
      let encodedUri = encodeURI(csvContent);
      let link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", "gel_annotations.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }

    window.onload = init;
  </script>
</body>
</html>
"""


def get_interactive_html() -> str:
    """Return the complete standalone HTML string for the interactive drag-and-drop gel annotator."""
    return HTML_TEMPLATE


def save_interactive_app(output_html_path: str = "gel_annotator.html") -> str:
    """Save the self-contained interactive drag-and-drop web application to an HTML file."""
    os.makedirs(os.path.dirname(os.path.abspath(output_html_path)), exist_ok=True)
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(HTML_TEMPLATE)
    return output_html_path


def calculate_ladder_standard_curve(
    ladder_bands_with_rf: List[Tuple[float, float]],
) -> Tuple[float, float, float]:
    """Calculate the logarithmic standard curve slope, intercept, and R^2 from ladder band (size, Rf) pairs.

    Relationship: log10(size) = slope * Rf + intercept
    """
    if len(ladder_bands_with_rf) < 2:
        raise ValueError("At least two calibration bands are required.")

    xs = [rf for _, rf in ladder_bands_with_rf]
    ys = [math.log10(size) for size, _ in ladder_bands_with_rf]
    n = len(xs)

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    ss_yy = sum((y - mean_y) ** 2 for y in ys)

    if ss_xx == 0:
        raise ValueError("Rf values cannot all be identical.")

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    r2 = (ss_xy ** 2) / (ss_xx * ss_yy) if (ss_xx * ss_yy) > 0 else 0.0

    return round(slope, 5), round(intercept, 5), round(r2, 4)


def estimate_band_mw(rf: float, slope: float, intercept: float) -> float:
    """Estimate molecular weight from Rf using calibrated log-linear parameters."""
    log_mw = slope * rf + intercept
    return round(10.0 ** log_mw, 1)


class StandaloneAppHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Quiet logging


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def launch_interactive_annotator(
    port: int = 8501,
    open_browser: bool = True,
    blocking: bool = False,
) -> str:
    """Launch the interactive drag-and-drop gel labeling tool on a local HTTP server."""
    server = ReusableTCPServer(("127.0.0.1", port), StandaloneAppHandler)
    actual_port = server.server_address[1]
    server_url = f"http://127.0.0.1:{actual_port}"

    if blocking:
        if open_browser:
            webbrowser.open(server_url)
        print(f"BioLabCalc Interactive Gel Annotator running at {server_url} (Press Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
    else:
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        if open_browser:
            webbrowser.open(server_url)

    return server_url
