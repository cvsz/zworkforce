document.addEventListener('DOMContentLoaded', () => {
  // Navigation
  const navItems = document.querySelectorAll('.nav-item');
  const sections = document.querySelectorAll('.view-section');

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = item.getAttribute('data-target');
      
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      sections.forEach(s => {
        if (s.id === targetId) {
          s.classList.add('active');
        } else {
          s.classList.remove('active');
        }
      });
    });
  });

  // Metrics WebSocket Connection
  let wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // Use a fallback URL if not running on the server directly
  let wsUrl = `${wsProtocol}//${window.location.host}/admin/ws/metrics`;
  if (window.location.protocol === 'file:') {
    wsUrl = `ws://localhost:8000/admin/ws/metrics`;
  }

  const connStatus = document.getElementById('connectionStatus');
  const pulseDot = document.querySelector('.pulse-dot');
  let ws;

  function connectWebSocket() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      connStatus.textContent = 'Connected Live';
      pulseDot.style.backgroundColor = 'var(--accent)';
      pulseDot.style.animation = 'pulse-dot 2s infinite';
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'metrics') {
        updateMetrics(msg.data);
      }
    };

    ws.onclose = () => {
      connStatus.textContent = 'Disconnected - Reconnecting...';
      pulseDot.style.backgroundColor = 'var(--danger)';
      pulseDot.style.animation = 'none';
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.error("WebSocket Error:", err);
    };
  }

  function updateMetrics(data) {
    document.getElementById('valActiveUploads').textContent = data.active_uploads;
    document.getElementById('valQueueDepth').textContent = data.queue_depth;
    document.getElementById('valAvgLatency').textContent = data.avg_latency_ms.toFixed(1);
    
    // Simulate RPS changing slightly for the visual effect if not provided
    const baseRps = data.requests_per_second || 1250;
    const jitter = Math.random() * 50 - 25;
    document.getElementById('valRps').textContent = Math.max(0, baseRps + jitter).toFixed(1);

    // Update trend color based on latency
    const trendLatency = document.getElementById('trendLatency');
    if (data.avg_latency_ms < 5) {
      trendLatency.className = 'metric-trend positive';
      trendLatency.textContent = 'Ultra Fast';
    } else if (data.avg_latency_ms < 20) {
      trendLatency.className = 'metric-trend neutral';
      trendLatency.textContent = 'Normal';
    } else {
      trendLatency.className = 'metric-trend negative';
      trendLatency.textContent = 'Degraded';
    }
  }

  // GraphQL Client
  const GQL_URL = window.location.protocol === 'file:' ? 'http://localhost:8000/admin/graphql' : '/admin/graphql';

  async function fetchGraphQL(query, variables = {}) {
    try {
      const res = await fetch(GQL_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, variables })
      });
      const json = await res.json();
      return json.data;
    } catch (e) {
      console.error("GraphQL Error:", e);
      return null;
    }
  }

  // Load Feature Flags
  async function loadFeatureFlags() {
    const query = `
      query {
        featureFlags {
          name
          enabled
          rolloutPercentage
          description
        }
      }
    `;
    const data = await fetchGraphQL(query);
    if (!data) return;

    // Use mock data if the API returns empty (for demonstration when redis is empty)
    let flags = data.featureFlags;
    if (!flags || flags.length === 0) {
      flags = [
        { name: 'delta_sync_v2', enabled: true, description: 'Delta synchronization v2' },
        { name: 'grpc_streaming', enabled: true, description: 'gRPC streaming support' },
        { name: 'ai_scan_enabled', enabled: false, description: 'AI-powered malware scanning' },
        { name: 'quantum_crypto', enabled: false, description: 'Quantum-resistant cryptography' }
      ];
    }

    const grid = document.getElementById('featureFlagsGrid');
    grid.innerHTML = '';

    flags.forEach(f => {
      const card = document.createElement('div');
      card.className = 'feature-card glass';
      
      card.innerHTML = `
        <div class="feature-card-header">
          <h4>${formatName(f.name)}</h4>
          <label class="switch">
            <input type="checkbox" ${f.enabled ? 'checked' : ''} data-flag="${f.name}">
            <span class="slider"></span>
          </label>
        </div>
        <p class="feature-desc">${f.description}</p>
        <div style="font-size: 0.8rem; color: var(--text-secondary)">
          Rollout: ${f.rolloutPercentage !== undefined ? f.rolloutPercentage : 100}%
        </div>
      `;
      grid.appendChild(card);
    });

    // Add listeners
    const toggles = grid.querySelectorAll('input[type="checkbox"]');
    toggles.forEach(t => {
      t.addEventListener('change', async (e) => {
        const flagName = e.target.getAttribute('data-flag');
        const isEnabled = e.target.checked;
        
        const mut = `
          mutation UpdateFlag($flag: FeatureFlagInput!) {
            updateFeatureFlag(flag: $flag) {
              name
              enabled
            }
          }
        `;
        await fetchGraphQL(mut, {
          flag: { name: flagName, enabled: isEnabled, rolloutPercentage: 100 }
        });
      });
    });
  }

  function formatName(name) {
    return name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  }

  // Load Mock Uploads
  function loadUploads() {
    const tbody = document.getElementById('uploadsTableBody');
    const mockUploads = [
      { id: 'sess-8923a', file: 'enterprise_dataset_2026.parquet', status: 'syncing', progress: 68, size: '4.2 GB' },
      { id: 'sess-4b82c', file: 'q3_financial_report.pdf', status: 'completed', progress: 100, size: '12 MB' },
      { id: 'sess-19ca2', file: 'machine_learning_weights.pt', status: 'validating', progress: 100, size: '8.4 GB' },
      { id: 'sess-f2910', file: 'user_avatars_batch_9.zip', status: 'pending', progress: 0, size: '540 MB' }
    ];

    tbody.innerHTML = '';
    mockUploads.forEach(u => {
      let badgeClass = 'pending';
      if (u.status === 'completed') badgeClass = 'success';
      
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family: 'JetBrains Mono', monospace; color: var(--text-secondary)">${u.id}</td>
        <td style="font-weight: 500">${u.file}</td>
        <td><span class="badge ${badgeClass}">${u.status.toUpperCase()}</span></td>
        <td style="width: 30%">
          <div style="display: flex; align-items: center; gap: 12px">
            <div class="progress-bg">
              <div class="progress-fill" style="width: ${u.progress}%"></div>
            </div>
            <span style="font-size: 0.8rem; color: var(--text-secondary)">${u.progress}%</span>
          </div>
        </td>
        <td style="color: var(--text-secondary)">${u.size}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Load Mock Telemetry
  function loadTelemetry() {
    const tbody = document.getElementById('telemetryTableBody');
    const actions = [
      { action: 'FILE_CHUNK_UPLOAD', resource: 's3://bucket/dataset', status: 'OK' },
      { action: 'AUTH_TOKEN_ROTATION', resource: 'user_svc', status: 'OK' },
      { action: 'GRPC_CLI_CMD', resource: 'wire_servicer', status: 'OK' },
      { action: 'DELTA_SYNC_PATCH', resource: 'app/services/delta', status: 'WARN' },
      { action: 'OPA_POLICY_CHECK', resource: 'auth_gateway', status: 'OK' }
    ];

    tbody.innerHTML = '';
    for(let i=0; i<8; i++) {
      const a = actions[Math.floor(Math.random() * actions.length)];
      const d = new Date(Date.now() - Math.floor(Math.random() * 10000));
      
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family: 'JetBrains Mono', monospace; color: var(--text-secondary)">${d.toISOString().split('T')[1].substring(0,8)}</td>
        <td style="font-weight: 500">${a.action}</td>
        <td style="color: var(--text-secondary)">${a.resource}</td>
        <td><span style="color: ${a.status === 'OK' ? 'var(--accent)' : 'var(--warning)'}">${a.status}</span></td>
      `;
      tbody.appendChild(tr);
    }
  }

  // Initialize
  connectWebSocket();
  loadFeatureFlags();
  loadUploads();
  loadTelemetry();
  
  // Refresh telemetry periodically
  setInterval(loadTelemetry, 5000);
});
