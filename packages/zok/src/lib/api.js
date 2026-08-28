function readCookie(name) {
  const prefix = `${name}=`;
  const match = document.cookie
    .split(';')
    .map(value => value.trim())
    .find(value => value.startsWith(prefix));

  if (!match) return '';
  try {
    return decodeURIComponent(match.slice(prefix.length));
  } catch {
    return '';
  }
}

export async function apiFetch(input, init = {}) {
  const headers = new Headers(init.headers || {});
  const method = String(init.method || 'GET').toUpperCase();
  const csrfToken = readCookie('zok_csrf');

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) {
    headers.set('X-CSRF-Token', csrfToken);
  }

  const response = await fetch(input, {
    ...init,
    credentials: 'same-origin',
    headers,
  });

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent('zok:unauthorized'));
  }

  return response;
}
