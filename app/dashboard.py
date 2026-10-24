DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flock Energy — Urja Smart Meter Ops Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    #map { height: 420px; border-radius: 0.75rem; }
  </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen">
  <!-- Navbar -->
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-lg">⚡</div>
        <div>
          <h1 class="text-base font-semibold leading-tight">Urja Meter Ops Modern Client</h1>
          <p class="text-xs text-slate-400">REST API Proxy Dashboard & Visual Analytics</p>
        </div>
      </div>
      <div class="flex items-center gap-3 text-xs">
        <span id="sync-status" class="px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">● API Connected</span>
        <a href="/docs" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition">Swagger /docs</a>
        <a href="/openapi.json" target="_blank" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition">OpenAPI JSON</a>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 py-6 space-y-6">
    <!-- KPI Cards -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
        <p class="text-xs text-slate-400 uppercase tracking-wider">Total Grid Meters</p>
        <p id="kpi-total" class="text-2xl font-bold mt-1 text-white">---</p>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
        <p class="text-xs text-emerald-400 uppercase tracking-wider">Installed (Active)</p>
        <p id="kpi-installed" class="text-2xl font-bold mt-1 text-emerald-400">---</p>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
        <p class="text-xs text-rose-400 uppercase tracking-wider">Faulty</p>
        <p id="kpi-faulty" class="text-2xl font-bold mt-1 text-rose-400">---</p>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
        <p class="text-xs text-amber-400 uppercase tracking-wider">Decommissioned</p>
        <p id="kpi-decom" class="text-2xl font-bold mt-1 text-amber-400">---</p>
      </div>
      <div class="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
        <p class="text-xs text-cyan-400 uppercase tracking-wider">Transformers (DTs)</p>
        <p id="kpi-dts" class="text-2xl font-bold mt-1 text-cyan-400">40</p>
      </div>
    </div>

    <!-- Map & Time Series Analytics Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Geospatial Grid Map -->
      <div class="lg:col-span-7 bg-slate-800/40 border border-slate-700/60 rounded-2xl p-4 space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold flex items-center gap-2">
            <span>🗺️ Grid Spatial Distribution</span>
            <span class="text-xs font-normal text-slate-400">(403 Smart Meters Mapped)</span>
          </h2>
          <div class="flex items-center gap-2 text-xs text-slate-400">
            <span class="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Installed
            <span class="inline-block w-2.5 h-2.5 rounded-full bg-rose-500 ml-2"></span> Faulty
            <span class="inline-block w-2.5 h-2.5 rounded-full bg-amber-500 ml-2"></span> Decom
          </div>
        </div>
        <div id="map"></div>
      </div>

      <!-- Selected Meter Detail & Consumption Chart -->
      <div class="lg:col-span-5 bg-slate-800/40 border border-slate-700/60 rounded-2xl p-4 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold flex items-center gap-2">
            <span>📈 Live Consumption & Voltage</span>
          </h2>
          <span id="chart-meter-badge" class="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">Meter J100000</span>
        </div>
        <div class="h-64">
          <canvas id="consumptionChart"></canvas>
        </div>
        <div id="meter-info-card" class="bg-slate-900/60 border border-slate-800 rounded-xl p-3 text-xs space-y-1">
          <div class="flex justify-between text-slate-400"><span>Serial / Make:</span><span id="info-serial" class="text-slate-200 font-mono">SE33962 (HPL)</span></div>
          <div class="flex justify-between text-slate-400"><span>Phase / DT:</span><span id="info-phase" class="text-slate-200">single (DT-001)</span></div>
          <div class="flex justify-between text-slate-400"><span>Substation / Feeder:</span><span id="info-hier" class="text-slate-200">SS-01 / F-001</span></div>
        </div>
      </div>
    </div>

    <!-- Meters Explorer & Filter Table -->
    <div class="bg-slate-800/40 border border-slate-700/60 rounded-2xl p-4 space-y-4">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <h2 class="text-sm font-semibold">⚡ Meter Inventory Explorer</h2>
        <div class="flex flex-wrap gap-2 text-xs">
          <input id="filter-search" type="text" placeholder="Search ID or Serial..." class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 focus:outline-none focus:border-emerald-500 w-44" />
          <select id="filter-make" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 focus:outline-none">
            <option value="">All Makes</option>
            <option value="HPL">HPL</option>
            <option value="Genus">Genus</option>
            <option value="Secure">Secure</option>
            <option value="L&T">L&T</option>
            <option value="Allied">Allied</option>
          </select>
          <select id="filter-status" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 focus:outline-none">
            <option value="">All Statuses</option>
            <option value="Installed">Installed</option>
            <option value="Faulty">Faulty</option>
            <option value="Decommissioned">Decommissioned</option>
          </select>
          <select id="filter-phase" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 focus:outline-none">
            <option value="">All Phases</option>
            <option value="single">Single Phase</option>
            <option value="three">Three Phase</option>
          </select>
          <button id="btn-apply-filter" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition">Filter</button>
          <button id="btn-export-csv" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium transition flex items-center gap-1.5">
            <span>📥 Export CSV</span>
          </button>
        </div>
      </div>

      <div class="overflow-x-auto rounded-xl border border-slate-700/60">
        <table class="w-full text-left text-xs text-slate-300">
          <thead class="bg-slate-900/80 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
            <tr>
              <th class="px-4 py-2.5">Meter ID</th>
              <th class="px-4 py-2.5">Serial</th>
              <th class="px-4 py-2.5">Make</th>
              <th class="px-4 py-2.5">Phase</th>
              <th class="px-4 py-2.5">Status</th>
              <th class="px-4 py-2.5">DT Code</th>
              <th class="px-4 py-2.5">Build</th>
              <th class="px-4 py-2.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody id="meters-table-body" class="divide-y divide-slate-800/80 bg-slate-900/30">
            <tr><td colspan="8" class="text-center py-6 text-slate-500">Loading meters...</td></tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between text-xs text-slate-400 pt-2">
        <span id="page-indicator">Showing page 1</span>
        <div class="flex gap-2">
          <button id="btn-prev" class="px-3 py-1 rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 disabled:opacity-40">Previous</button>
          <button id="btn-next" class="px-3 py-1 rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 disabled:opacity-40">Next</button>
        </div>
      </div>
    </div>
  </main>

  <script>
    let map, chart;
    let currentPage = 1;
    let markersLayer = L.layerGroup();

    async function initDashboard() {
      // 1. Initialize Map
      map = L.map('map').setView([26.9124, 75.7873], 12);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap'
      }).addTo(map);
      markersLayer.addTo(map);

      // 2. Initialize Chart
      const ctx = document.getElementById('consumptionChart').getContext('2d');
      chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Voltage R (V)',
              data: [],
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              yAxisID: 'yVoltage',
              tension: 0.3
            },
            {
              label: 'Energy (kWh)',
              data: [],
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              yAxisID: 'yEnergy',
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            yVoltage: { type: 'linear', position: 'left', grid: { color: 'rgba(255,255,255,0.05)' } },
            yEnergy: { type: 'linear', position: 'right', grid: { drawOnChartArea: false } },
            x: { grid: { color: 'rgba(255,255,255,0.05)' } }
          },
          plugins: { legend: { labels: { color: '#94a3b8' } } }
        }
      });

      // 3. Load Initial Data
      await loadMetricsAndPins();
      await loadMetersTable(1);
      await loadMeterConsumption('J100000');

      // Bind events
      document.getElementById('btn-apply-filter').addEventListener('click', () => loadMetersTable(1));
      document.getElementById('btn-export-csv').addEventListener('click', exportCSV);
      document.getElementById('btn-prev').addEventListener('click', () => { if (currentPage > 1) loadMetersTable(currentPage - 1); });
      document.getElementById('btn-next').addEventListener('click', () => loadMetersTable(currentPage + 1));
    }

    function exportCSV() {
      const q = document.getElementById('filter-search').value.trim();
      const make = document.getElementById('filter-make').value;
      const status = document.getElementById('filter-status').value;
      const phase = document.getElementById('filter-phase').value;

      let url = '/api/v1/meters/export/csv?';
      const params = [];
      if (q) params.push(`q=${encodeURIComponent(q)}`);
      if (make) params.push(`make=${encodeURIComponent(make)}`);
      if (status) params.push(`install_status=${encodeURIComponent(status)}`);
      if (phase) params.push(`phase_type=${encodeURIComponent(phase)}`);
      window.location.href = url + params.join('&');
    }

    async function loadMetricsAndPins() {
      try {
        const res = await fetch('/api/v1/meters?page_size=100');
        const firstBatch = await res.json();
        const total = firstBatch.total;
        document.getElementById('kpi-total').textContent = total;

        // Fetch all meters to plot pins
        const allRes = await fetch(`/api/v1/meters?page_size=${total}`);
        const allData = await allRes.json();
        
        let installed = 0, faulty = 0, decom = 0;
        markersLayer.clearLayers();

        allData.data.forEach(m => {
          if (m.install_status === 'Installed') installed++;
          else if (m.install_status === 'Faulty') faulty++;
          else if (m.install_status === 'Decommissioned') decom++;

          if (m.geo && m.geo.latitude && m.geo.longitude) {
            const color = m.install_status === 'Installed' ? '#10b981' : (m.install_status === 'Faulty' ? '#f43f5e' : '#f59e0b');
            const circle = L.circleMarker([m.geo.latitude, m.geo.longitude], {
              radius: 5,
              fillColor: color,
              color: '#0f172a',
              weight: 1,
              opacity: 1,
              fillOpacity: 0.85
            });
            circle.bindPopup(`<b>Meter: ${m.meter_id}</b><br/>Serial: ${m.serial_no}<br/>Make: ${m.make}<br/>Status: ${m.install_status}<br/><button onclick="loadMeterConsumption('${m.meter_id}')" class="mt-1 text-emerald-400 underline">View Readings</button>`);
            markersLayer.addLayer(circle);
          }
        });

        document.getElementById('kpi-installed').textContent = installed;
        document.getElementById('kpi-faulty').textContent = faulty;
        document.getElementById('kpi-decom').textContent = decom;
      } catch (err) {
        console.error('Error loading metrics:', err);
      }
    }

    async function loadMetersTable(page) {
      currentPage = page;
      const q = document.getElementById('filter-search').value.trim();
      const make = document.getElementById('filter-make').value;
      const status = document.getElementById('filter-status').value;
      const phase = document.getElementById('filter-phase').value;

      let url = `/api/v1/meters?page=${page}&page_size=10`;
      if (q) url += `&q=${encodeURIComponent(q)}`;
      if (make) url += `&make=${encodeURIComponent(make)}`;
      if (status) url += `&install_status=${encodeURIComponent(status)}`;
      if (phase) url += `&phase_type=${encodeURIComponent(phase)}`;

      const res = await fetch(url);
      const data = await res.json();
      
      const tbody = document.getElementById('meters-table-body');
      tbody.innerHTML = '';
      if (!data.data || data.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-slate-500">No meters found matching criteria.</td></tr>';
        return;
      }

      data.data.forEach(m => {
        const badgeColor = m.install_status === 'Installed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : (m.install_status === 'Faulty' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20');
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/50 transition';
        tr.innerHTML = `
          <td class="px-4 py-2 font-medium text-slate-200">${m.meter_id}</td>
          <td class="px-4 py-2 font-mono">${m.serial_no}</td>
          <td class="px-4 py-2">${m.make}</td>
          <td class="px-4 py-2">${m.phase_type}</td>
          <td class="px-4 py-2"><span class="px-2 py-0.5 rounded text-[10px] border ${badgeColor}">${m.install_status}</span></td>
          <td class="px-4 py-2 font-mono">${m.dt_code || '—'}</td>
          <td class="px-4 py-2 text-slate-400">${m.build || '—'}</td>
          <td class="px-4 py-2 text-right">
            <button onclick="loadMeterConsumption('${m.meter_id}')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">View Data</button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      document.getElementById('page-indicator').textContent = `Page ${data.page} of ${data.total_pages} (${data.total} total)`;
      document.getElementById('btn-prev').disabled = data.page <= 1;
      document.getElementById('btn-next').disabled = data.page >= data.total_pages;
    }

    async function loadMeterConsumption(meterId) {
      document.getElementById('chart-meter-badge').textContent = `Meter ${meterId}`;
      try {
        const [consRes, detRes] = await Promise.all([
          fetch(`/api/v1/meters/${meterId}/consumption`),
          fetch(`/api/v1/meters/${meterId}`)
        ]);
        
        if (detRes.ok) {
          const det = await detRes.json();
          document.getElementById('info-serial').textContent = `${det.serial_no} (${det.make})`;
          document.getElementById('info-phase').textContent = `${det.phase_type} (${det.dt_code || '—'})`;
          const hier = det.hierarchy;
          const ss = hier && hier.substation ? hier.substation.name : '—';
          const f = hier && hier.feeder ? hier.feeder.name : '—';
          document.getElementById('info-hier').textContent = `${ss} / ${f}`;
        }

        if (consRes.ok) {
          const cons = await consRes.json();
          const labels = cons.readings.map(r => r.timestamp.split('T')[1] || r.timestamp);
          const voltages = cons.readings.map(r => r.volt_r);
          const energies = cons.readings.map(r => r.kwh);

          chart.data.labels = labels;
          chart.data.datasets[0].data = voltages;
          chart.data.datasets[1].data = energies;
          chart.update();
        }
      } catch (e) {
        console.error('Error fetching consumption:', e);
      }
    }

    window.addEventListener('DOMContentLoaded', initDashboard);
  </script>
</body>
</html>
"""
