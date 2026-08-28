const content = document.querySelector('#content');
const classification = document.querySelector('#classification');
const reason = document.querySelector('#reason');
const proposalOutput = document.querySelector('#proposal');
const memories = document.querySelector('#memories');
const search = document.querySelector('#search');
const status = document.querySelector('#status');
let pendingProposal = null;

function setStatus(message) { status.textContent = message; }

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message || 'Request failed');
  return payload;
}

async function loadMemories() {
  setStatus('กำลังโหลด memory…');
  try {
    const payload = await request(`/v1/memories?q=${encodeURIComponent(search.value.trim())}`);
    memories.replaceChildren();
    for (const memory of payload.memories) {
      const item = document.createElement('li');
      const title = document.createElement('strong');
      title.textContent = `${memory.classification} · revision ${memory.revision}`;
      const body = document.createElement('p');
      body.textContent = memory.content;
      const meta = document.createElement('small');
      meta.textContent = `expires ${memory.expires_at} · ${memory.provenance.source_type}:${memory.provenance.source_id}`;
      const remove = document.createElement('button');
      remove.textContent = 'ลบถาวร';
      remove.addEventListener('click', async () => {
        if (!confirm('ยืนยันการลบ memory และทุก revision?')) return;
        await request(`/v1/memories/${memory.memory_id}`, {
          method: 'DELETE',
          headers: { 'x-zarvis-confirm-delete': memory.memory_id },
        });
        await loadMemories();
      });
      item.append(title, body, meta, remove);
      memories.append(item);
    }
    setStatus(`โหลดแล้ว ${payload.memories.length} รายการ`);
  } catch (error) {
    setStatus(error.message);
  }
}

async function proposeMemory() {
  setStatus('กำลังสร้างข้อเสนอ…');
  try {
    pendingProposal = await request('/v1/memory/proposals', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        schema_version: 'zarvis.memory.proposal-requested.v1',
        content: content.value,
        classification: classification.value,
        reason: reason.value,
        confidence: 1,
        provenance: {
          source_type: 'owner',
          source_id: 'privacy-console',
        },
      }),
    });
    proposalOutput.textContent = JSON.stringify(pendingProposal, null, 2);
    const confirmButton = document.createElement('button');
    confirmButton.textContent = 'ยืนยันข้อเสนอนี้';
    confirmButton.addEventListener('click', confirmProposal, { once: true });
    proposalOutput.after(confirmButton);
    setStatus('ตรวจข้อเสนอและกดยืนยัน');
  } catch (error) {
    setStatus(error.message);
  }
}

async function confirmProposal(event) {
  try {
    await request(`/v1/memory/proposals/${pendingProposal.proposal_id}/confirm`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        approval_digest: pendingProposal.approval_digest,
        approval_nonce: pendingProposal.approval_nonce,
      }),
    });
    event.currentTarget.remove();
    content.value = '';
    setStatus('บันทึก memory หลังยืนยันแล้ว');
    await loadMemories();
  } catch (error) {
    setStatus(error.message);
  }
}

async function exportMemories() {
  try {
    const payload = await request('/v1/memories/export');
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'zarvis-memory-export.json';
    link.click();
    URL.revokeObjectURL(url);
    setStatus('Export สำเร็จ');
  } catch (error) {
    setStatus(error.message);
  }
}

document.querySelector('#propose').addEventListener('click', proposeMemory);
document.querySelector('#refresh').addEventListener('click', loadMemories);
document.querySelector('#export').addEventListener('click', exportMemories);
search.addEventListener('input', () => void loadMemories());
void loadMemories();
