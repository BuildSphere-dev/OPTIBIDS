// admin.js — OPTIBOTS Premium Frontend (Rebuilt)

const admin = {

  /* =================================================
     LOAD STATS (for dashboard counters)
  ================================================= */
  async loadStats() {
    try {
      const [tenders, apps, accepted] = await Promise.all([
        api.get('/admin/tenders'),
        api.get('/admin/applications'),
        api.get('/admin/accepted-offers'),
      ]);

      const el = id => document.getElementById(id);

      if(el('stat-tenders'))  el('stat-tenders').textContent  = Array.isArray(tenders)  ? tenders.length  : '—';
      if(el('stat-apps'))     el('stat-apps').textContent     = Array.isArray(apps)     ? apps.length     : '—';
      if(el('stat-accepted')) el('stat-accepted').textContent = Array.isArray(accepted) ? accepted.length  : '—';
      if(el('stat-pending')) {
        const pending = Array.isArray(apps) ? apps.filter(a => a.status === 'submitted').length : 0;
        el('stat-pending').textContent = pending;
      }
    } catch(e) { console.warn('Stats load failed', e); }
  },

  /* =================================================
     LOAD TENDERS
  ================================================= */
  async loadTenders() {
    const box = document.getElementById('tenders-list');
    if (!box) return;

    box.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading tenders…</p></div>';

    try {
      const tenders = await api.get('/admin/tenders');

      if (!Array.isArray(tenders) || !tenders.length) {
        box.innerHTML = '<div class="empty-state"><i class="fas fa-file-contract"></i><p>No tenders yet. <a href="create_tender.html">Create your first tender</a>.</p></div>';
        return;
      }

      box.innerHTML = '';
      tenders.forEach(t => {
        const div = document.createElement('div');
        div.className = 'tender-item';

        const attachment = (t.files && t.files.length)
          ? `<a class="auth-btn small" href="http://localhost:8000/download/${t.files[0]}" target="_blank" style="margin-top:.5rem;"><i class="fas fa-download"></i> Download</a>`
          : '';

        div.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:.5rem;margin-bottom:.5rem;">
            <h3 style="margin:0;">${t.title}</h3>
            <span class="badge ${t.status}">${t.status}</span>
          </div>
          <p style="font-size:0.875rem;">${t.description ? t.description.slice(0, 160) + (t.description.length > 160 ? '…' : '') : ''}</p>
          <p style="font-size:0.8rem;color:var(--text-3);margin:.4rem 0;">
            <i class="fas fa-users" style="margin-right:.3rem;"></i>${t.applicant_count ?? 0} application(s)
          </p>
          <div class="card-actions">
            ${attachment}
            <button class="auth-btn small" onclick="admin.viewApplicants(${t.id})">
              <i class="fas fa-users"></i> View Applicants
            </button>
            <button class="auth-btn small primary" onclick="admin.runSummary(${t.id})">
              <i class="fas fa-robot"></i> AI Summary
            </button>
          </div>
          <div id="summary-${t.id}" style="display:none;margin-top:1rem;"></div>
        `;
        box.appendChild(div);
      });

    } catch(err) {
      box.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>Failed to load tenders.</p></div>';
    }
  },

  /* =================================================
     RECENT APPLICATIONS
  ================================================= */
  async loadRecentApps() {
    const box = document.getElementById('recent-apps');
    if (!box) return;

    box.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading…</p></div>';

    try {
      const apps = await api.get('/admin/applications');

      if (!Array.isArray(apps) || !apps.length) {
        box.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>No applications yet.</p></div>';
        return;
      }

      box.innerHTML = '';
      apps.slice(0, 8).forEach(a => {
        const div = document.createElement('div');
        div.className = `tender-item status-${a.status}`;
        div.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem;">
            <div>
              <p style="font-weight:600;color:var(--text);font-size:0.92rem;">${a.user_email}</p>
              <p style="font-size:0.82rem;color:var(--text-2);margin:.15rem 0;">${a.tender_title}</p>
            </div>
            <span class="badge ${a.status}">${a.status}</span>
          </div>
          <div class="card-actions">
            <button class="auth-btn small" onclick="admin.reviewApplication(${a.id})">
              <i class="fas fa-eye"></i> Review
            </button>
          </div>
        `;
        box.appendChild(div);
      });

    } catch(err) {
      box.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>Failed to load applications.</p></div>';
    }
  },

  /* =================================================
     REVIEW APPLICATION
  ================================================= */
  reviewApplication(appId) {
    localStorage.setItem('review_app_id', appId);
    window.location.href = '/admin/review_application.html';
  },

  viewApplicants(tenderId) {
    localStorage.setItem('view_tender_id', tenderId);
    window.location.href = '/admin/view_tender.html';
  },

  /* =================================================
     AI SUMMARY (inline on dashboard)
  ================================================= */
  async runSummary(tenderId) {
    const panel = document.getElementById(`summary-${tenderId}`);
    if (!panel) return;

    panel.style.display = 'block';
    panel.innerHTML = `
      <div class="ai-panel">
        <div class="ai-panel-header">
          <div class="ai-icon"><i class="fas fa-robot"></i></div>
          <div><h3>Running AI Evaluation…</h3><p style="font-size:0.78rem;color:var(--text-3);margin:0;">This may take 10–30 seconds</p></div>
        </div>
        <div class="loading-state" style="padding:1.5rem 0;"><div class="spinner"></div></div>
      </div>`;

    try {
      const res = await api.post(`/admin/tenders/${tenderId}/summary`, {});

      if (res.error) {
        panel.innerHTML = `<div class="ai-panel"><p style="color:var(--text-2);">${res.error}</p></div>`;
        return;
      }

      const best = res.best_application;
      const others = res.comparison || [];

      if (!best) {
        panel.innerHTML = `
          <div class="ai-panel">
            <div class="ai-panel-header">
              <div class="ai-icon"><i class="fas fa-robot"></i></div>
              <div><h3>AI Evaluation Report</h3><p style="font-size:0.78rem;color:var(--text-3);margin:0;">Powered by phi3:mini</p></div>
            </div>
            <p style="padding:1rem 0;margin:0;color:var(--text-2);">No evaluated proposals found for this tender yet. Wait for the background scoring task to complete before generating the report.</p>
          </div>`;
        return;
      }

      panel.innerHTML = `
        <div class="ai-panel">
          <div class="ai-panel-header">
            <div class="ai-icon"><i class="fas fa-robot"></i></div>
            <div><h3>AI Evaluation Report</h3><p style="font-size:0.78rem;color:var(--text-3);margin:0;">Powered by phi3:mini</p></div>
          </div>
          <div class="best-applicant-card">
            <h4><i class="fas fa-trophy"></i> Best Applicant</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;font-size:0.88rem;">
              <div><span style="color:var(--text-3);font-size:0.76rem;display:block;">EMAIL</span><strong>${best.email || '—'}</strong></div>
              <div><span style="color:var(--text-3);font-size:0.76rem;display:block;">SCORE</span><strong>${best.overall_score !== undefined ? best.overall_score.toFixed(1) : '—'}</strong></div>
              <div><span style="color:var(--text-3);font-size:0.76rem;display:block;">STATUS</span><strong>${best.status || '—'}</strong></div>
              <div><span style="color:var(--text-3);font-size:0.76rem;display:block;">EVALUATED</span><strong>${best.created_at ? new Date(best.created_at).toLocaleString() : '—'}</strong></div>
            </div>
            ${best.summary ? `<p style="margin-top:.75rem;font-size:0.85rem;color:var(--text-2);">${best.summary}</p>` : `<p style="margin-top:.75rem;font-size:0.85rem;color:var(--text-2);">No summary available yet.</p>`}
          </div>
          ${others.length ? `
            <h4 style="font-size:0.9rem;margin-bottom:.6rem;color:var(--text-2);">All Applications</h4>
            <div style="overflow-x:auto;">
              <table class="comparison-table">
                <thead><tr><th>Email</th><th>Score</th><th>Status</th><th>Summary</th></tr></thead>
                <tbody>${others.map(a => `
                  <tr>
                    <td>${a.email || '—'}</td>
                    <td>${a.overall_score !== undefined ? a.overall_score.toFixed(1) : '—'}</td>
                    <td>${a.status || '—'}</td>
                    <td style="color:var(--accent-green);">${a.summary || '—'}</td>
                  </tr>`).join('')}
                </tbody>
              </table>
            </div>` : ''}
        </div>`;

    } catch(err) {
      panel.innerHTML = `<div class="ai-panel"><p style="color:var(--accent-red);"><i class="fas fa-exclamation-circle"></i> AI evaluation failed. Ensure Ollama is running.</p></div>`;
    }
  },
};

window.admin = admin;
