const tokenInput = document.querySelector('#token');
const connection = document.querySelector('#connection');
const actionsNode = document.querySelector('#actions');
const logNode = document.querySelector('#log');

let ownerToken = sessionStorage.getItem('zarvisLocalOwnerToken') ?? '';
tokenInput.value = ownerToken;

function log(value) {
  logNode.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

async function api(path, options = {}) {
  if (!ownerToken) throw new Error('Enter the local owner token first.');
  const headers = new Headers(options.headers ?? {});
  headers.set('authorization', `Bearer ${ownerToken}`);
  if (options.body && !headers.has('content-type')) headers.set('content-type', 'application/json');
  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${payload.error ?? response.status}: ${payload.message ?? 'Request failed'}`);
  return payload;
}

function button(label, handler, disabled = false, className = '') {
  const node = document.createElement('button');
  node.textContent = label;
  node.disabled = disabled;
  node.className = className;
  node.addEventListener('click', async () => {
    node.disabled = true;
    try {
      await handler();
      await refresh();
    } catch (error) {
      log(error.message);
    } finally {
      node.disabled = disabled;
    }
  });
  return node;
}

function renderAction(action) {
  const article = document.createElement('article');
  article.className = 'action';
  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.innerHTML = `<div><strong>${action.capability}</strong><br><code>${action.key}</code>: ${String(action.previous_value)} → ${String(action.next_value)}</div><span class="badge">${action.status}</span>`;
  const impact = document.createElement('p');
  impact.textContent = `Target: ${action.impact.target}. External effects: ${action.impact.external_side_effects ? 'yes' : 'none'}.`;
  const controls = document.createElement('div');
  controls.className = 'controls';

  if (action.status === 'pending_approval') {
    controls.append(button('Approve exact preview', async () => {
      const result = await api(`/v1/actions/${encodeURIComponent(action.action_id)}/approve`, {
        method: 'POST',
        body: JSON.stringify({
          approval_digest: action.approval_digest,
          approval_nonce: action.approval_nonce,
        }),
      });
      log(result);
    }));
  }
  if (action.status === 'executed') {
    controls.append(button('Roll back', async () => {
      const result = await api(`/v1/actions/${encodeURIComponent(action.action_id)}/rollback`, {
        method: 'POST',
        body: JSON.stringify({
          rollback_digest: action.rollback_digest,
          rollback_nonce: action.rollback_nonce,
        }),
      });
      log(result);
    }, false, 'secondary'));
  }

  article.append(meta, impact, controls);
  return article;
}

async function refresh() {
  const [status, listing] = await Promise.all([api('/v1/status'), api('/v1/actions')]);
  connection.textContent = status.emergency_stop ? 'Emergency stop active' : 'Unlocked · local only';
  actionsNode.replaceChildren(...listing.actions.map(renderAction));
  if (!listing.actions.length) actionsNode.textContent = 'No local actions yet.';
}

document.querySelector('#save-token').addEventListener('click', async () => {
  ownerToken = tokenInput.value;
  sessionStorage.setItem('zarvisLocalOwnerToken', ownerToken);
  try { await refresh(); } catch (error) { log(error.message); }
});

document.querySelector('#refresh').addEventListener('click', () => refresh().catch((error) => log(error.message)));

document.querySelector('#preview-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const result = await api('/v1/actions/preview', {
      method: 'POST',
      body: JSON.stringify({
        capability: 'sandbox.preference.set',
        key: document.querySelector('#key').value,
        value: document.querySelector('#value').value,
      }),
    });
    log(result);
    await refresh();
  } catch (error) {
    log(error.message);
  }
});

document.querySelector('#stop').addEventListener('click', async () => {
  try {
    log(await api('/v1/emergency-stop', { method: 'POST', body: JSON.stringify({ reason: 'owner_console' }) }));
    await refresh();
  } catch (error) { log(error.message); }
});

document.querySelector('#resume').addEventListener('click', async () => {
  try {
    log(await api('/v1/emergency-resume', { method: 'POST', body: JSON.stringify({ confirmation: 'RESUME_LOCAL_ACTIONS' }) }));
    await refresh();
  } catch (error) { log(error.message); }
});

if (ownerToken) refresh().catch(() => {});
