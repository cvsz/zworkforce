const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '::1', '[::1]', 'ollama']);
const ENGLISH_MUTATION_PATTERN = /\b(delete|remove|erase|drop|destroy|deploy|restart|reboot|shutdown|stop|start|install|uninstall|update|upgrade|push|merge|commit|send|publish|pay|transfer|buy|sell)\b/iu;
const THAI_MUTATION_PATTERN = /(ลบ|ถอน|ทำลาย|ติดตั้ง|ถอนการติดตั้ง|อัปเดต|อัปเกรด|รีสตาร์ต|รีบูต|ปิดเครื่อง|หยุดบริการ|เริ่มบริการ|ดีพลอย|พุช|เมิร์จ|คอมมิต|ส่ง|เผยแพร่|จ่าย|โอน|ซื้อ|ขาย)/u;

export class LocalConversationError extends Error {
  constructor(message, { code = 'local_conversation_failed', status = 502 } = {}) {
    super(message);
    this.name = 'LocalConversationError';
    this.code = code;
    this.status = status;
  }
}

export function validateLocalLlmBaseUrl(value) {
  if (typeof value !== 'string' || !value.trim()) {
    throw new LocalConversationError('Local LLM endpoint is not configured.', {
      code: 'local_llm_not_configured',
      status: 503,
    });
  }
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new LocalConversationError('Local LLM endpoint is invalid.', {
      code: 'invalid_local_llm_url',
      status: 503,
    });
  }
  if (url.protocol !== 'http:' || !LOOPBACK_HOSTS.has(url.hostname) || url.username || url.password) {
    throw new LocalConversationError('Local conversation endpoint must use an allowlisted local HTTP host.', {
      code: 'non_local_llm_denied',
      status: 503,
    });
  }
  url.pathname = url.pathname.replace(/\/$/, '');
  url.search = '';
  url.hash = '';
  return url;
}

export function classifyLocalConversation(text) {
  const normalized = String(text || '').trim();
  return {
    mutation_requested: ENGLISH_MUTATION_PATTERN.test(normalized)
      || THAI_MUTATION_PATTERN.test(normalized),
    text: normalized,
  };
}

export function createApprovalRequiredResponse({ commandId, sessionId, locale = 'th-TH' }) {
  const thai = locale.toLowerCase().startsWith('th');
  return {
    schema_version: 'zarvis.command.completed.v1',
    command_id: commandId,
    session_id: sessionId,
    completed_at: new Date().toISOString(),
    status: 'approval_required',
    replayed: false,
    intent: { name: 'owner.action.preview-required', source: 'local_safety_boundary' },
    result: {
      local_only: true,
      mutation_executed: false,
      approval_surface: 'https://zarvis.zeaz.dev',
    },
    speech: {
      locale,
      text: thai
        ? 'คำสั่งนี้อาจเปลี่ยนแปลงระบบ ฉันยังไม่ได้ดำเนินการ กรุณาสร้างและยืนยันพรีวิวใน Owner Action Console ก่อน'
        : 'This request may change the system. I did not execute it. Create and approve an exact preview in the Owner Action Console first.',
    },
    safety: {
      owner_approval_required: true,
      mutation_executed: false,
    },
  };
}

export async function executeLocalConversation({
  commandId,
  sessionId,
  text,
  locale = 'th-TH',
}, {
  baseUrl,
  model = 'qwen3:8b',
  apiKey = '',
  fetchImpl = fetch,
  timeoutMs = 45_000,
} = {}) {
  const classification = classifyLocalConversation(text);
  if (!classification.text) {
    throw new LocalConversationError('Conversation text is required.', {
      code: 'invalid_conversation_text',
      status: 400,
    });
  }
  if (classification.mutation_requested) {
    return createApprovalRequiredResponse({ commandId, sessionId, locale });
  }

  const endpoint = validateLocalLlmBaseUrl(baseUrl);
  endpoint.pathname = `${endpoint.pathname}/chat/completions`.replace(/\/+/g, '/');
  const headers = { 'content-type': 'application/json' };
  if (apiKey) headers.authorization = `Bearer ${apiKey}`;

  let response;
  try {
    response = await fetchImpl(endpoint, {
      method: 'POST',
      headers,
      redirect: 'error',
      signal: AbortSignal.timeout(timeoutMs),
      body: JSON.stringify({
        model,
        stream: false,
        temperature: 0.35,
        messages: [
          {
            role: 'system',
            content: [
              'You are Z.A.R.V.I.S., the private local assistant for PHIPHAT PHOEMSUK.',
              'Reply in the same language as the owner, using Thai when the owner speaks Thai.',
              'Be concise, accurate, calm, and useful.',
              'Never claim that you executed, changed, installed, deleted, deployed, paid, sent, or published anything.',
              'Any request that can mutate a system requires an exact preview and owner approval in the Owner Action Console.',
              'All inference is local. Do not suggest sending private audio or transcripts to cloud services.',
            ].join(' '),
          },
          { role: 'user', content: classification.text },
        ],
      }),
    });
  } catch (error) {
    throw new LocalConversationError(`Local Ollama request failed: ${error.message}`, {
      code: 'local_llm_unavailable',
      status: 503,
    });
  }

  const payload = await response.json().catch(() => ({}));
  const answer = payload?.choices?.[0]?.message?.content?.trim();
  if (!response.ok || !answer) {
    throw new LocalConversationError('Local Ollama did not return a usable response.', {
      code: 'local_llm_response_invalid',
      status: 502,
    });
  }

  return {
    schema_version: 'zarvis.command.completed.v1',
    command_id: commandId,
    session_id: sessionId,
    completed_at: new Date().toISOString(),
    status: 'completed',
    replayed: false,
    intent: { name: 'local.conversation.respond', source: 'local_fallback' },
    result: {
      local_only: true,
      model,
      mutation_executed: false,
    },
    speech: { locale, text: answer },
    safety: {
      owner_approval_required: false,
      mutation_executed: false,
    },
  };
}
