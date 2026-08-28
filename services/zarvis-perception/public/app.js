const purpose = document.querySelector('#purpose');
const sessionOutput = document.querySelector('#session');
const resultOutput = document.querySelector('#result');
const status = document.querySelector('#status');
const activateButton = document.querySelector('#activate');
const stopButton = document.querySelector('#stop');
const uploadButton = document.querySelector('#upload');
const screenButton = document.querySelector('#screen');
const cameraButton = document.querySelector('#camera');
const fileInput = document.querySelector('#file');
const history = document.querySelector('#history');
let currentSession = null;

function setStatus(message) { status.textContent = message; }

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message || 'Request failed');
  return payload;
}

function selectedModalities() {
  return [...document.querySelectorAll('.checks input:checked')].map((input) => input.value);
}

function updateButtons() {
  const active = currentSession?.status === 'active';
  activateButton.disabled = currentSession?.status !== 'pending_consent';
  stopButton.disabled = !active;
  uploadButton.disabled = !active;
  screenButton.disabled = !active || !currentSession.modalities.includes('screen');
  cameraButton.disabled = !active || !currentSession.modalities.includes('camera');
}

function renderSession(session) {
  currentSession = session;
  sessionOutput.textContent = JSON.stringify(session, null, 2);
  updateButtons();
}

async function createSession() {
  setStatus('กำลังสร้าง consent proposal…');
  try {
    renderSession(await request('/v1/perception/sessions', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        purpose: purpose.value,
        modalities: selectedModalities(),
        retention_minutes: 60,
      }),
    }));
    setStatus('ตรวจรายละเอียดแล้วกดยืนยันเพื่อเปิด session');
  } catch (error) { setStatus(error.message); }
}

async function activateSession() {
  try {
    renderSession(await request(`/v1/perception/sessions/${currentSession.session_id}/activate`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        consent_digest: currentSession.consent_digest,
        consent_nonce: currentSession.consent_nonce,
      }),
    }));
    setStatus('Session เปิดใช้งานสำหรับ one-shot capture แล้ว');
  } catch (error) { setStatus(error.message); }
}

async function stopSession() {
  try {
    renderSession(await request(`/v1/perception/sessions/${currentSession.session_id}/stop`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: '{}',
    }));
    setStatus('หยุด session แล้ว');
    await loadHistory();
  } catch (error) { setStatus(error.message); }
}

function bytesToBase64(bytes) {
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

async function analyzeBytes(bytes, { modality, mediaType, sourceName }) {
  setStatus('กำลังวิเคราะห์และ redact ข้อมูล…');
  try {
    const result = await request(`/v1/perception/sessions/${currentSession.session_id}/media`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        source_modality: modality,
        media_type: mediaType,
        source_name: sourceName,
        captured_at: new Date().toISOString(),
        content_base64: bytesToBase64(bytes),
      }),
    });
    resultOutput.textContent = JSON.stringify(result, null, 2);
    setStatus('วิเคราะห์สำเร็จ โดยไม่เก็บ raw media');
    await loadHistory();
  } catch (error) { setStatus(error.message); }
}

async function uploadFile() {
  const file = fileInput.files?.[0];
  if (!file) return setStatus('กรุณาเลือกไฟล์');
  const modality = file.type.startsWith('image/') ? 'image' : 'document';
  if (!currentSession.modalities.includes(modality)) return setStatus(`Session ไม่ได้อนุญาต ${modality}`);
  await analyzeBytes(new Uint8Array(await file.arrayBuffer()), {
    modality,
    mediaType: file.type,
    sourceName: file.name,
  });
}

async function oneShotCapture(kind) {
  let stream;
  try {
    setStatus(kind === 'screen' ? 'เลือกหน้าจอสำหรับ snapshot 1 ภาพ' : 'กำลังเปิดกล้องสำหรับ snapshot 1 ภาพ');
    stream = kind === 'screen'
      ? await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false })
      : await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    const video = document.createElement('video');
    video.srcObject = stream;
    video.muted = true;
    await video.play();
    await new Promise((resolve) => requestAnimationFrame(resolve));
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('ไม่สามารถสร้าง snapshot ได้');
    await analyzeBytes(new Uint8Array(await blob.arrayBuffer()), {
      modality: kind,
      mediaType: 'image/png',
      sourceName: `${kind}-snapshot.png`,
    });
  } catch (error) {
    setStatus(error.message || 'Capture failed');
  } finally {
    for (const track of stream?.getTracks() || []) track.stop();
  }
}

async function loadHistory() {
  try {
    const payload = await request('/v1/perception/sessions');
    history.replaceChildren();
    for (const session of payload.sessions) {
      const item = document.createElement('li');
      const title = document.createElement('strong');
      title.textContent = `${session.status} · ${session.purpose}`;
      const meta = document.createElement('small');
      meta.textContent = `${session.modalities.join(', ')} · results ${session.results.length} · expires ${session.retention_expires_at}`;
      const remove = document.createElement('button');
      remove.textContent = 'ลบ Analysis ถาวร';
      remove.addEventListener('click', async () => {
        if (!confirm('ยืนยันการลบ perception session และ encrypted analysis ทั้งหมด?')) return;
        await request(`/v1/perception/sessions/${session.session_id}`, {
          method: 'DELETE',
          headers: { 'x-zarvis-confirm-delete': session.session_id },
        });
        if (currentSession?.session_id === session.session_id) {
          currentSession = null;
          sessionOutput.textContent = 'ยังไม่มี session';
          updateButtons();
        }
        await loadHistory();
      });
      item.append(title, meta, remove);
      history.append(item);
    }
  } catch (error) { setStatus(error.message); }
}

document.querySelector('#create').addEventListener('click', createSession);
activateButton.addEventListener('click', activateSession);
stopButton.addEventListener('click', stopSession);
uploadButton.addEventListener('click', uploadFile);
screenButton.addEventListener('click', () => oneShotCapture('screen'));
cameraButton.addEventListener('click', () => oneShotCapture('camera'));
document.querySelector('#refresh').addEventListener('click', loadHistory);
void loadHistory();
