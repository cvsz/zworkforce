const input = document.querySelector('#command-input');
const listenButton = document.querySelector('#listen-button');
const sendButton = document.querySelector('#send-button');
const speakToggle = document.querySelector('#speak-toggle');
const responseElement = document.querySelector('#assistant-response');
const factsElement = document.querySelector('#repository-facts');
const timeline = document.querySelector('#timeline');
const statusElement = document.querySelector('#system-status');
const intentBadge = document.querySelector('#intent-badge');
const orb = document.querySelector('#orb');

const sessionId = globalThis.crypto?.randomUUID?.() ?? `session-${Date.now()}`;
let activeModality = 'text';
let recognition;

function setStatus(text, state = 'idle') {
  statusElement.textContent = text;
  orb.dataset.state = state;
}

function appendTimeline(text) {
  const item = document.createElement('li');
  const time = new Intl.DateTimeFormat('th-TH', { timeStyle: 'medium' }).format(new Date());
  item.textContent = `${time} — ${text}`;
  timeline.prepend(item);
}

function renderFacts(repository) {
  const rows = [
    ['Repository', repository.full_name],
    ['Visibility', repository.visibility],
    ['Default branch', repository.default_branch],
    ['Open issues + PRs', repository.open_issues_count],
    ['Latest push', repository.pushed_at],
  ];

  factsElement.replaceChildren();
  for (const [label, value] of rows) {
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = String(value);
    factsElement.append(dt, dd);
  }
}

function speak(text, locale) {
  if (!speakToggle.checked || !('speechSynthesis' in globalThis)) {
    return;
  }
  globalThis.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = locale || 'th-TH';
  globalThis.speechSynthesis.speak(utterance);
}

async function sendCommand() {
  const text = input.value.trim();
  if (!text) {
    setStatus('กรุณาระบุคำสั่ง', 'error');
    return;
  }

  sendButton.disabled = true;
  listenButton.disabled = true;
  setStatus('กำลังประมวลผล', 'working');
  appendTimeline(`รับคำสั่งแบบ ${activeModality}`);

  try {
    const response = await fetch('/api/command', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        schema_version: 'zarvis.command.requested.v1',
        session_id: sessionId,
        input: {
          modality: activeModality,
          text,
          locale: 'th-TH',
        },
      }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.error?.message ?? 'Command failed.');
    }

    responseElement.textContent = payload.speech.text;
    intentBadge.textContent = payload.intent.name;
    renderFacts(payload.result);
    appendTimeline(`เรียก ${payload.intent.name} สำเร็จ · audit ${payload.audit.event_id}`);
    speak(payload.speech.text, payload.speech.locale);
    setStatus('ดำเนินการสำเร็จ', 'success');
  } catch (error) {
    responseElement.textContent = error.message;
    intentBadge.textContent = 'failed';
    appendTimeline(`คำสั่งล้มเหลว: ${error.message}`);
    setStatus('ดำเนินการไม่สำเร็จ', 'error');
  } finally {
    sendButton.disabled = false;
    listenButton.disabled = false;
    activeModality = 'text';
  }
}

const SpeechRecognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = 'th-TH';
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.addEventListener('start', () => {
    activeModality = 'voice';
    setStatus('กำลังฟัง', 'listening');
    listenButton.textContent = 'กำลังฟัง…';
  });

  recognition.addEventListener('result', (event) => {
    const transcript = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join(' ')
      .trim();
    input.value = transcript;
    if (event.results[event.results.length - 1].isFinal) {
      appendTimeline('แปลงเสียงเป็นข้อความแล้ว');
      void sendCommand();
    }
  });

  recognition.addEventListener('end', () => {
    listenButton.textContent = 'เริ่มฟังเสียง';
    if (orb.dataset.state === 'listening') {
      setStatus('พร้อมรับคำสั่ง');
    }
  });

  recognition.addEventListener('error', (event) => {
    appendTimeline(`ระบบรับเสียงผิดพลาด: ${event.error}`);
    setStatus('ไม่สามารถรับเสียงได้', 'error');
  });

  listenButton.addEventListener('click', () => recognition.start());
} else {
  listenButton.disabled = true;
  listenButton.textContent = 'Browser ไม่รองรับ Speech Recognition';
}

sendButton.addEventListener('click', () => void sendCommand());
input.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    void sendCommand();
  }
});
