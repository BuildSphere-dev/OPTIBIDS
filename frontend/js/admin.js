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
          </div>
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
     POPULATE TENDER SELECT (for dashboard AI panel)
  ================================================= */
  async populateTenderSelect() {
    const sel = document.getElementById('ai-tender-select');
    const note = document.getElementById('ai-tender-select-note');
    if (!sel) return;

    try {
      const [tenders, apps] = await Promise.all([
        api.get('/admin/tenders'),
        api.get('/admin/applications'),
      ]);

      sel.disabled = false;
      sel.innerHTML = '<option value="">— Select a Tender or Recent Application —</option>';

      let added = 0;
      if (Array.isArray(tenders) && tenders.length) {
        tenders.forEach(t => {
          const opt = document.createElement('option');
          opt.value = t.id;
          opt.textContent = t.title || `Tender #${t.id}`;
          sel.appendChild(opt);
          added += 1;
        });
      }

      if (Array.isArray(apps) && apps.length) {
        const recent = apps.slice(0, 8);
        const sep = document.createElement('option');
        sep.textContent = '―― Recent applications ――';
        sep.disabled = true;
        sep.className = 'disabled-option';
        sel.appendChild(sep);

        recent.forEach(a => {
          const opt = document.createElement('option');
          opt.value = a.tender_id;
          opt.textContent = `${a.user_email || 'Unknown applicant'} — ${a.tender_title || 'Untitled tender'}`;
          sel.appendChild(opt);
          added += 1;
        });
      }

      if (!added) {
        sel.innerHTML = '<option value="" disabled>No tenders or recent applications available</option>';
        sel.disabled = true;
        if (note) note.textContent = 'No data found. Create a tender or submit an application first.';
      } else if (note) {
        note.textContent = 'Choose a tender or recent application to evaluate.';
      }

      sel.addEventListener('change', () => {
        const btn = document.getElementById('ai-eval-btn');
        if (btn) btn.disabled = !sel.value;
        const res = document.getElementById('ai-eval-result');
        if (res) res.innerHTML = '';
      });
    } catch(e) {
      sel.innerHTML = '<option value="" disabled>Unable to load tenders/applications</option>';
      sel.disabled = true;
      if (note) note.textContent = 'Could not load selection data. Check your session or API connectivity.';
      console.warn('populateTenderSelect failed', e);
    }
  },

  /* =================================================
     DASHBOARD AI EVALUATION (top-5, show more)
  ================================================= */
  async runDashboardAI() {
    const sel    = document.getElementById('ai-tender-select');
    const btn    = document.getElementById('ai-eval-btn');
    const panel  = document.getElementById('ai-eval-result');
    if (!sel || !panel) return;

    const tenderId = sel.value;
    if (!tenderId) return;

    const SHOW = 5;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running AI Pipeline…';
    panel.innerHTML = `
      <div class="ai-panel">
        <div class="ai-panel-header">
          <div class="ai-icon"><i class="fas fa-robot"></i></div>
          <div><h3>Evaluating proposals…</h3><p style="font-size:0.78rem;color:var(--text-3);margin:0;">This may take 10–30 seconds</p></div>
        </div>
        <div class="loading-state" style="padding:1.5rem 0;"><div class="spinner"></div></div>
      </div>`;

    try {
      const res = await api.post(`/admin/tenders/${tenderId}/summary`, {});

      if (res.error) {
        panel.innerHTML = `<div class="ai-panel"><p style="color:var(--text-2);">${res.error}</p></div>`;
        return;
      }

      const best    = res.best_application;
      const allApps = res.comparison || [];
      const visible = allApps.slice(0, SHOW);
      const hidden  = allApps.slice(SHOW);

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

      const rowsHtml = (rows, startRank) => rows.map((a, i) => `
        <tr${a.application_id === best.application_id ? ' style="background:var(--bg2);"' : ''}>
          <td><span style="color:var(--text-3);margin-right:.4rem;">#${startRank + i}</span>${a.email || '—'}</td>
          <td><strong style="color:var(--primary-light);">${a.overall_score !== undefined ? a.overall_score.toFixed(1) : '—'}</strong></td>
          <td>${a.status || '—'}</td>
          <td style="color:var(--accent-green);font-size:0.82rem;">${a.summary || '—'}</td>
          <td><button class="auth-btn small" onclick="admin.reviewApplication(${a.application_id})"><i class="fas fa-eye"></i></button></td>
        </tr>`).join('');

      const hiddenId  = `hidden-rows-${tenderId}`;
      const showMoreId = `show-more-${tenderId}`;

      panel.innerHTML = `
        <div class="ai-panel">
          <div class="ai-panel-header">
            <div class="ai-icon"><i class="fas fa-robot"></i></div>
            <div>
              <h3>AI Evaluation Report</h3>
              <p style="font-size:0.78rem;color:var(--text-3);margin:0;">Powered by phi3:mini · ${allApps.length} application(s) evaluated</p>
            </div>
          </div>

          <div class="best-applicant-card" style="margin-bottom:1.25rem;">
            <h4><i class="fas fa-trophy"></i> Best Applicant</h4>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.75rem;font-size:0.88rem;">
              <div><span style="color:var(--text-3);font-size:0.76rem;display:block;margin-bottom:.1rem;">EMAIL</span><strong>${best.email || '—'}</strong></div>
              <div><span style="color:var(--text-3);font-size:0.76rem;display:block;margin-bottom:.1rem;">SCORE</span><strong>${best.overall_score !== undefined ? best.overall_score.toFixed(1) : '—'}</strong></div>
              <div><span style="color:var(--text-3);font-size:0.76rem;display:block;margin-bottom:.1rem;">STATUS</span><strong>${best.status || '—'}</strong></div>
              <div><span style="color:var(--text-3);font-size:0.76rem;display:block;margin-bottom:.1rem;">EVALUATED</span><strong>${best.created_at ? new Date(best.created_at).toLocaleString() : '—'}</strong></div>
            </div>
            ${best.summary ? `<p style="margin-top:.75rem;font-size:0.85rem;color:var(--text-2);">${best.summary}</p>` : `<p style="margin-top:.75rem;font-size:0.85rem;color:var(--text-2);">No summary available yet.</p>`}
            ${best.note ? `<p style="margin-top:.5rem;font-size:0.8rem;color:var(--text-3);">${best.note}</p>` : ''}
            <button class="auth-btn small primary" style="margin-top:.75rem;" onclick="admin.reviewApplication(${best.application_id})">
              <i class="fas fa-eye"></i> Review Best Applicant
            </button>
          </div>

          ${allApps.length ? `
            <h4 style="font-size:0.9rem;margin-bottom:.6rem;color:var(--text-2);">
              All Applications
              <span style="font-weight:400;color:var(--text-3);font-size:0.8rem;margin-left:.4rem;">
                Showing ${Math.min(SHOW, allApps.length)} of ${allApps.length}
              </span>
            </h4>
            <div style="overflow-x:auto;">
              <table class="comparison-table">
                <thead><tr><th>Email</th><th>Score</th><th>Status</th><th>Summary</th><th></th></tr></thead>
                <tbody id="visible-rows-${tenderId}">
                  ${rowsHtml(visible, 1)}
                </tbody>
                ${hidden.length ? `<tbody id="${hiddenId}" style="display:none;">${rowsHtml(hidden, SHOW + 1)}</tbody>` : ''}
              </table>
            </div>
            ${hidden.length ? `
              <button class="auth-btn small" id="${showMoreId}" style="margin-top:.75rem;"
                onclick="admin._toggleMoreRows('${hiddenId}','${showMoreId}',${hidden.length})">
                <i class="fas fa-chevron-down"></i> Show ${hidden.length} more application(s)
              </button>` : ''}
          ` : ''}
        </div>`;

    } catch(err) {
      panel.innerHTML = `<div class="ai-panel"><p style="color:var(--accent-red);"><i class="fas fa-exclamation-circle"></i> AI evaluation failed. Ensure Ollama is running.</p></div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-magic"></i> Regenerate Summary';
    }
  },

  _toggleMoreRows(tbodyId, btnId, count) {
    const tbody = document.getElementById(tbodyId);
    const btn   = document.getElementById(btnId);
    if (!tbody || !btn) return;
    const isHidden = tbody.style.display === 'none';
    tbody.style.display = isHidden ? '' : 'none';
    btn.innerHTML = isHidden
      ? `<i class="fas fa-chevron-up"></i> Show less`
      : `<i class="fas fa-chevron-down"></i> Show ${count} more application(s)`;
  },

};

window.admin = admin;