// applicant.js — OPTIBOTS Premium Frontend (Rebuilt)

const applicant = {

  /* =================================================
     LOAD PUBLIC TENDERS
  ================================================= */
  async loadTenders() {
    const box = document.getElementById('public-tenders');
    if (!box) return;

    box.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading tenders…</p></div>';

    try {
      const tenders = await api.get('/tenders');

      if (!Array.isArray(tenders) || !tenders.length) {
        box.innerHTML = '<div class="empty-state"><i class="fas fa-file-contract"></i><p>No public tenders available right now.</p></div>';
        return;
      }

      box.innerHTML = '';
      tenders.forEach(t => {
        const div = document.createElement('div');
        div.className = 'tender-item';
        // Store title safely as a data attribute to avoid quote escaping in onclick
        div.dataset.tenderTitle = t.title;

        div.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:.5rem;margin-bottom:.5rem;">
            <h3 style="margin:0;font-size:1rem;">${t.title}</h3>
            <span class="badge public">Open</span>
          </div>
          <p style="font-size:0.875rem;">${t.description ? t.description.slice(0, 200) + (t.description.length > 200 ? '…' : '') : ''}</p>
          <div class="card-actions">
            <button class="auth-btn small primary"
              data-tender-id="${t.id}"
              data-tender-title="${t.title.replace(/"/g, '&quot;')}"
              onclick="applicant.openApplyForm(this)">
              <i class="fas fa-paper-plane"></i> Apply Now
            </button>
          </div>
        `;
        box.appendChild(div);
      });

    } catch(e) {
      box.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>Failed to load tenders.</p></div>';
    }
  },

  /* =================================================
     OPEN APPLY MODAL (called from Apply Now button)
  ================================================= */
  openApplyForm(btn) {
    const tenderId    = btn.dataset.tenderId;
    const tenderTitle = btn.dataset.tenderTitle;

    // Fill the hidden fields that submitProposal() reads
    const idEl = document.getElementById('apply-tender-id');
    const nameEl = document.getElementById('tender-name-display');
    const textEl = document.getElementById('apply-text');
    const msgEl  = document.getElementById('apply-msg');
    const modal  = document.getElementById('apply-modal');

    if (!idEl || !modal) {
      console.error('Modal elements missing');
      return;
    }

    idEl.value = tenderId;
    if (nameEl)  nameEl.textContent = '📋 ' + (tenderTitle || 'Tender #' + tenderId);
    if (textEl)  textEl.value = '';
    if (msgEl)   msgEl.textContent = '';

    modal.classList.add('open');
  },

  /* =================================================
     LOAD NOTIFICATIONS (OFFERS)
  ================================================= */
  async loadNotifications() {
    const box = document.getElementById('notifications');
    if (!box) return;

    box.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Checking for offers…</p></div>';

    try {
      const offers = await api.get('/applicant/notifications');

      if (!offers.length) {
        box.innerHTML = '<div class="empty-state" style="padding:1.5rem;"><i class="fas fa-bell-slash"></i><p>No pending offers at this time.</p></div>';
        return;
      }

      box.innerHTML = '';
      offers.forEach(o => {
        const div = document.createElement('div');
        div.className = 'offer-card';
        div.dataset.applicationId = o.application_id;
        div.style.marginBottom = '1rem';

        div.innerHTML = `
          <h4><i class="fas fa-bell"></i> Offer for Tender #${o.tender_id}</h4>
          <p style="margin:.6rem 0 .8rem;">${o.offer?.message || 'No offer details provided.'}</p>
          <div class="card-actions">
            <button class="auth-btn small primary"
              onclick="applicant.respondOffer(${o.application_id}, 'accept')">
              <i class="fas fa-check"></i> Accept
            </button>
            <button class="auth-btn small danger"
              onclick="applicant.respondOffer(${o.application_id}, 'reject')">
              <i class="fas fa-times"></i> Decline
            </button>
          </div>
        `;
        box.appendChild(div);
      });

    } catch(e) {
      box.innerHTML = '<div class="empty-state" style="padding:1rem;"><p>Failed to load notifications.</p></div>';
    }
  },

  /* =================================================
     RESPOND TO OFFER
  ================================================= */
  async respondOffer(appId, decision) {
    try {
      await api.post(`/applicant/offer/${appId}/respond?decision=${decision}`);
      const msg = decision === 'accept' ? '🎉 Offer accepted! Check My Contracts.' : 'Offer declined.';
      showToastGlobal(msg, decision === 'accept' ? 'success' : 'info');

      const card = document.querySelector(`.offer-card[data-application-id="${appId}"]`);
      if (card) card.remove();

      const badge = document.getElementById('notif-badge');
      if (badge) {
        const cur = parseInt(badge.textContent) || 0;
        const next = Math.max(0, cur - 1);
        if (next <= 0) {
          badge.style.display = 'none';
        } else {
          badge.textContent = next;
        }
      }

      const box = document.getElementById('notifications');
      if (box && !box.querySelector('.offer-card')) {
        box.innerHTML = '<div class="empty-state" style="padding:1.5rem;"><i class="fas fa-bell-slash"></i><p>No pending offers at this time.</p></div>';
      }
    } catch(e) {
      showToastGlobal('Failed to respond to offer', 'error');
    }
  },
};

function showToastGlobal(msg, type='info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const icons = { success:'fa-check-circle', error:'fa-times-circle', info:'fa-info-circle' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<i class="fas ${icons[type] || 'fa-info-circle'}"></i><span>${msg}</span>`;
  container.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

window.applicant = applicant;
window.showToast = showToastGlobal;
