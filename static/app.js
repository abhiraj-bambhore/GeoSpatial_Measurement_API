// Apple-style Minimalist Geospatial Application Logic

document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const browseBtn = document.getElementById('browse-btn');
  const uploadStatus = document.getElementById('upload-status');
  const statusText = document.getElementById('status-text');

  const fileInfoSection = document.getElementById('file-info-section');
  const measurementsSection = document.getElementById('measurements-section');
  const historySection = document.getElementById('history-section');

  const infoId = document.getElementById('info-id');
  const infoFilename = document.getElementById('info-filename');
  const infoCrs = document.getElementById('info-crs');
  const infoCount = document.getElementById('info-count');
  const infoStatusPill = document.getElementById('info-status-pill');
  const linkFileJson = document.getElementById('link-file-json');
  const linkMeasurementsJson = document.getElementById('link-measurements-json');

  const measurementsTbody = document.getElementById('measurements-tbody');
  const historyTbody = document.getElementById('history-tbody');
  const refreshHistoryBtn = document.getElementById('refresh-history-btn');
  const searchInput = document.getElementById('search-input');
  const filterPills = document.querySelectorAll('.pill');

  const exportJsonBtn = document.getElementById('export-json-btn');
  const exportCsvBtn = document.getElementById('export-csv-btn');

  // Modal Elements
  const featureModal = document.getElementById('feature-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalSubtitle = document.getElementById('modal-subtitle');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const modalDoneBtn = document.getElementById('modal-done-btn');
  const modalGeomType = document.getElementById('modal-geom-type');
  const modalMeasType = document.getElementById('modal-meas-type');
  const modalMeasVal = document.getElementById('modal-meas-val');
  const modalMeasUnit = document.getElementById('modal-meas-unit');
  const modalWkt = document.getElementById('modal-wkt');
  const copyWktBtn = document.getElementById('copy-wkt-btn');
  const modalPropertiesContainer = document.getElementById('modal-properties-container');
  const geomSvg = document.getElementById('geom-svg');
  const geomCanvasCaption = document.getElementById('geom-canvas-caption');

  let currentMeasurements = [];
  let currentFilter = 'all';
  let currentFile = null;

  // Drag and drop event listeners
  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  browseBtn.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleFileUpload(fileInput.files[0]);
    }
  });

  refreshHistoryBtn.addEventListener('click', loadHistory);

  // Filter pills
  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentFilter = pill.getAttribute('data-filter');
      renderMeasurementsTable();
    });
  });

  // Search input
  searchInput.addEventListener('input', () => {
    renderMeasurementsTable();
  });

  // Export handlers
  exportJsonBtn.addEventListener('click', exportAsJson);
  exportCsvBtn.addEventListener('click', exportAsCsv);

  // Modal event listeners
  modalCloseBtn.addEventListener('click', closeModal);
  modalDoneBtn.addEventListener('click', closeModal);
  featureModal.addEventListener('click', (e) => {
    if (e.target === featureModal) closeModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !featureModal.classList.contains('hidden')) {
      closeModal();
    }
  });

  copyWktBtn.addEventListener('click', () => {
    const text = modalWkt.textContent;
    navigator.clipboard.writeText(text).then(() => {
      copyWktBtn.textContent = 'Copied!';
      setTimeout(() => { copyWktBtn.textContent = 'Copy WKT'; }, 1800);
    });
  });

  async function handleFileUpload(file) {
    const fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.zip') && !fileName.endsWith('.kml')) {
      alert('Invalid file format. Please upload a .zip (Shapefile) or .kml file.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    uploadStatus.classList.remove('hidden');
    statusText.textContent = `Uploading and processing ${file.name}...`;

    try {
      const response = await fetch('/api/files/', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Processing failed');
      }

      const fileData = await response.json();
      currentFile = fileData;
      displayFileInfo(fileData);
      await loadMeasurements(fileData.id);
      loadHistory();
    } catch (err) {
      console.error('Upload error:', err);
      alert(`Error processing file: ${err.message}`);
    } finally {
      uploadStatus.classList.add('hidden');
      fileInput.value = '';
    }
  }

  function displayFileInfo(data) {
    currentFile = data;
    fileInfoSection.classList.remove('hidden');
    infoId.textContent = `ID: ${data.id}`;
    infoFilename.textContent = data.filename;
    infoCrs.textContent = data.crs || 'Unknown';
    infoCount.textContent = data.feature_count.toLocaleString();

    infoStatusPill.className = 'badge';
    if (data.status === 'COMPLETED') {
      infoStatusPill.classList.add('badge-completed');
      infoStatusPill.textContent = 'COMPLETED';
    } else if (data.status === 'FAILED') {
      infoStatusPill.classList.add('badge-failed');
      infoStatusPill.textContent = 'FAILED';
    } else {
      infoStatusPill.classList.add('badge-processing');
      infoStatusPill.textContent = data.status || 'PROCESSING';
    }

    linkFileJson.href = `/api/files/${data.id}/`;
    linkFileJson.textContent = `GET /api/files/${data.id}/`;
    linkMeasurementsJson.href = `/api/files/${data.id}/measurements/`;
    linkMeasurementsJson.textContent = `GET /api/files/${data.id}/measurements/`;
  }

  async function loadMeasurements(fileId) {
    try {
      const response = await fetch(`/api/files/${fileId}/measurements/`);
      if (!response.ok) throw new Error('Failed to load measurements');

      const data = await response.json();
      currentMeasurements = data.measurements || [];
      measurementsSection.classList.remove('hidden');
      renderMeasurementsTable();
      measurementsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      console.error('Error fetching measurements:', err);
    }
  }

  function renderMeasurementsTable() {
    const query = searchInput.value.toLowerCase().trim();

    const filtered = currentMeasurements.filter(m => {
      if (currentFilter !== 'all') {
        if (currentFilter === 'Other') {
          if (['Polygon', 'LineString', 'Point'].includes(m.geometry_type)) {
            return false;
          }
        } else if (m.geometry_type !== currentFilter) {
          return false;
        }
      }

      if (query) {
        const indexStr = String(m.feature_index);
        const geomStr = (m.geometry_type || '').toLowerCase();
        const propsStr = JSON.stringify(m.properties || {}).toLowerCase();
        return indexStr.includes(query) || geomStr.includes(query) || propsStr.includes(query);
      }

      return true;
    });

    if (filtered.length === 0) {
      measurementsTbody.innerHTML = `<tr><td colspan="7" class="empty-state">No matching features found.</td></tr>`;
      return;
    }

    measurementsTbody.innerHTML = filtered.map(m => {
      let valFormatted = '-';
      let unitLabel = '-';

      if (m.measurement_value !== null && m.measurement_value !== undefined) {
        valFormatted = m.measurement_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
        if (m.measurement_unit === 'sq_meters') unitLabel = 'm²';
        else if (m.measurement_unit === 'meters') unitLabel = 'm';
        else unitLabel = m.measurement_unit || '-';
      }

      const propsJson = JSON.stringify(m.properties || {});

      return `
        <tr data-index="${m.feature_index}">
          <td>#${m.feature_index}</td>
          <td><span class="geom-tag">${escapeHtml(m.geometry_type)}</span></td>
          <td>${escapeHtml(m.measurement_type || 'none')}</td>
          <td><span class="val-bold">${valFormatted}</span></td>
          <td>${unitLabel}</td>
          <td><div class="properties-pre" title="${escapeHtml(propsJson)}">${escapeHtml(propsJson)}</div></td>
          <td>
            <button class="button button-secondary inspect-btn" data-index="${m.feature_index}" style="padding: 4px 10px; font-size: 11px;">
              Inspect
            </button>
          </td>
        </tr>
      `;
    }).join('');

    // Attach row and button click events to open detail modal
    measurementsTbody.querySelectorAll('tr').forEach(tr => {
      tr.addEventListener('click', (e) => {
        const idx = parseInt(tr.getAttribute('data-index'), 10);
        const feature = currentMeasurements.find(m => m.feature_index === idx);
        if (feature) openFeatureModal(feature);
      });
    });
  }

  function openFeatureModal(feature) {
    modalTitle.textContent = `Feature #${feature.feature_index}`;
    modalSubtitle.textContent = `${feature.geometry_type} — ${currentFile ? currentFile.filename : 'File'}`;

    modalGeomType.textContent = feature.geometry_type;
    modalMeasType.textContent = feature.measurement_type || 'none';

    if (feature.measurement_value !== null && feature.measurement_value !== undefined) {
      modalMeasVal.textContent = feature.measurement_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
      modalMeasUnit.textContent = feature.measurement_unit === 'sq_meters' ? 'sq_meters (m²)' : (feature.measurement_unit === 'meters' ? 'meters (m)' : feature.measurement_unit);
    } else {
      modalMeasVal.textContent = '-';
      modalMeasUnit.textContent = '-';
    }

    modalWkt.textContent = feature.geometry_wkt || 'No WKT geometry available';

    // Render properties table
    const props = feature.properties || {};
    const propKeys = Object.keys(props);
    if (propKeys.length === 0) {
      modalPropertiesContainer.innerHTML = '<div style="padding: 12px; font-size: 12px; color: var(--text-tertiary);">No attributes or properties defined.</div>';
    } else {
      modalPropertiesContainer.innerHTML = `
        <table class="prop-table">
          ${propKeys.map(k => `
            <tr>
              <td class="prop-key">${escapeHtml(k)}</td>
              <td class="prop-val">${escapeHtml(String(props[k]))}</td>
            </tr>
          `).join('')}
        </table>
      `;
    }

    // Render SVG visual representation
    renderGeometrySvg(feature.geometry_wkt, feature.geometry_type);

    featureModal.classList.remove('hidden');
  }

  function closeModal() {
    featureModal.classList.add('hidden');
  }

  function renderGeometrySvg(wkt, geomType) {
    geomSvg.innerHTML = '';
    if (!wkt) {
      geomCanvasCaption.textContent = 'No geometry coordinates to render.';
      return;
    }

    try {
      // Extract numeric coordinate pairs from WKT
      const matches = wkt.match(/[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+/g);
      if (!matches || matches.length === 0) {
        geomCanvasCaption.textContent = 'Coordinate parsing unavailable for this geometry.';
        return;
      }

      const points = matches.map(pair => {
        const [x, y] = pair.trim().split(/\s+/).map(Number);
        return { x, y };
      });

      // Calculate bounding box
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      points.forEach(pt => {
        if (pt.x < minX) minX = pt.x;
        if (pt.x > maxX) maxX = pt.x;
        if (pt.y < minY) minY = pt.y;
        if (pt.y > maxY) maxY = pt.y;
      });

      const widthSpan = maxX - minX || 0.0001;
      const heightSpan = maxY - minY || 0.0001;

      // Map to 400x240 SVG with padding
      const pad = 36;
      const w = 400 - (pad * 2);
      const h = 240 - (pad * 2);

      const toSvgCoords = (pt) => {
        const normX = (pt.x - minX) / widthSpan;
        const normY = (pt.y - minY) / heightSpan;
        // Flip Y because screen coordinates point down
        const svgX = pad + (normX * w);
        const svgY = 240 - pad - (normY * h);
        return { x: svgX, y: svgY };
      };

      const svgPts = points.map(toSvgCoords);

      if (geomType === 'Point' || svgPts.length === 1) {
        const pt = svgPts[0];
        geomSvg.innerHTML = `
          <circle cx="${pt.x}" cy="${pt.y}" r="18" fill="rgba(0, 113, 227, 0.15)"/>
          <circle cx="${pt.x}" cy="${pt.y}" r="8" fill="#0071e3"/>
          <circle cx="${pt.x}" cy="${pt.y}" r="3" fill="#ffffff"/>
        `;
        geomCanvasCaption.textContent = `Point coordinate: (${points[0].x.toFixed(5)}, ${points[0].y.toFixed(5)})`;
      } else if (geomType === 'LineString' || geomType === 'MultiLineString') {
        const polylinePts = svgPts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
        const vertexDots = svgPts.map(p => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3.5" fill="#0071e3" stroke="#fff" stroke-width="1.5"/>`).join('');

        geomSvg.innerHTML = `
          <polyline points="${polylinePts}" fill="none" stroke="#0071e3" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
          ${vertexDots}
        `;
        geomCanvasCaption.textContent = `LineString trajectory: ${points.length} vertices plotted`;
      } else {
        // Polygon / MultiPolygon
        const polygonPts = svgPts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
        const vertexDots = svgPts.map(p => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3" fill="#0071e3" stroke="#fff" stroke-width="1"/>`).join('');

        geomSvg.innerHTML = `
          <polygon points="${polygonPts}" fill="rgba(0, 113, 227, 0.12)" stroke="#0071e3" stroke-width="2" stroke-linejoin="round"/>
          ${vertexDots}
        `;
        geomCanvasCaption.textContent = `Polygon boundary: ${points.length} boundary coordinates`;
      }
    } catch (err) {
      console.warn('SVG geometry plot error:', err);
      geomCanvasCaption.textContent = 'Geometry representation generated from WKT.';
    }
  }

  // Export functions
  function exportAsJson() {
    if (!currentMeasurements || currentMeasurements.length === 0) {
      alert('No measurements available to export.');
      return;
    }

    const exportData = {
      file: currentFile,
      exported_at: new Date().toISOString(),
      measurements: currentMeasurements,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `measurements_${currentFile ? currentFile.filename : 'export'}.json`);
  }

  function exportAsCsv() {
    if (!currentMeasurements || currentMeasurements.length === 0) {
      alert('No measurements available to export.');
      return;
    }

    const headers = ['feature_index', 'geometry_type', 'measurement_type', 'measurement_value', 'measurement_unit', 'properties'];
    const rows = currentMeasurements.map(m => {
      return [
        m.feature_index,
        `"${m.geometry_type || ''}"`,
        `"${m.measurement_type || ''}"`,
        m.measurement_value !== null ? m.measurement_value : '',
        `"${m.measurement_unit || ''}"`,
        `"${JSON.stringify(m.properties || {}).replace(/"/g, '""')}"`,
      ].join(',');
    });

    const csvContent = [headers.join(','), ...rows].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    downloadBlob(blob, `measurements_${currentFile ? currentFile.filename : 'export'}.csv`);
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function loadHistory() {
    try {
      const response = await fetch('/api/files/');
      if (!response.ok) return;

      const data = await response.json();
      const files = data.files || [];

      if (files.length === 0) {
        historyTbody.innerHTML = `<tr><td colspan="7" class="empty-state">No processed files yet.</td></tr>`;
        return;
      }

      historyTbody.innerHTML = files.map(f => {
        let statusBadge = 'badge-pending';
        if (f.status === 'COMPLETED') statusBadge = 'badge-completed';
        else if (f.status === 'FAILED') statusBadge = 'badge-failed';

        const createdDate = f.created_at ? new Date(f.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' }) : '-';

        return `
          <tr>
            <td><code class="code-id">${f.id.substring(0, 8)}...</code></td>
            <td>${escapeHtml(f.filename)}</td>
            <td>${escapeHtml(f.crs || 'Unknown')}</td>
            <td>${f.feature_count}</td>
            <td><span class="badge ${statusBadge}">${f.status}</span></td>
            <td>${createdDate}</td>
            <td>
              <button class="button button-secondary view-btn" data-id="${f.id}" style="padding: 4px 10px; font-size: 11px;">
                View
              </button>
            </td>
          </tr>
        `;
      }).join('');

      document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const id = e.target.getAttribute('data-id');
          const fileResp = await fetch(`/api/files/${id}/`);
          if (fileResp.ok) {
            const fileData = await fileResp.json();
            displayFileInfo(fileData);
            await loadMeasurements(id);
          }
        });
      });
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Initial history load
  loadHistory();
});
