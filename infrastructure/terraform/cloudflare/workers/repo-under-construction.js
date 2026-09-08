const REPO_ALIASES = Object.freeze({
  'zwf': 'zworkforce',
  'zwf-api': 'zworkforce',
  'zslog': 'zworkforce',
  'zarvis': 'zworkforce',
  'studio': 'zsp-aitool',
  'zider': 'zsp-aitool',
  'chat': 'open-webui',
  'qwen': 'qwen-gen',
  'zai': 'zeaz-ai-command-center',
  'zdash': 'zdash',
  'zttshop': 'zttshop-php',
  'cme': 'cmeerp',
  'autoc': 'zworkforce',
  'zany': 'zanything',
  'zmovie': 'zmovie',
  'zasi': 'zasi',
  'zsme': 'zsme',
  'zaffiliate': 'zaffiliate',
  'zomega': 'zomega',
  'zksato': 'zksato',
  'stremdbc': 'stremdbc',
});

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function repoForHost(hostname) {
  const label = String(hostname || '').toLowerCase().split('.')[0];
  return REPO_ALIASES[label] || label;
}

function page(hostname, repo) {
  const host = escapeHtml(hostname);
  const repoName = escapeHtml(repo);
  const repoUrl = `https://github.com/cvsz/${encodeURIComponent(repo)}`;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>${host} · Under Construction</title>
<style>
:root{color-scheme:dark;--bg:#080b11;--panel:#111722;--line:#28344a;--text:#f3f6ff;--muted:#9ba9bf;--accent:#9bb7ff}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at top,#192642 0,#080b11 48%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{width:min(760px,100%);padding:42px;border:1px solid var(--line);border-radius:24px;background:rgba(17,23,34,.94);box-shadow:0 24px 80px rgba(0,0,0,.32)}
.badge{display:inline-flex;padding:7px 11px;border:1px solid #4a5f87;border-radius:999px;color:var(--accent);font-size:13px}h1{font-size:clamp(40px,8vw,76px);letter-spacing:-.055em;margin:20px 0 12px;line-height:.95}p{color:var(--muted);font-size:17px;line-height:1.65}.repo{margin-top:28px;padding:16px;border:1px solid var(--line);border-radius:14px;background:#0b1018}.repo strong{display:block;color:var(--text);margin-bottom:5px}a{color:var(--accent);text-decoration:none}footer{margin-top:26px;font-size:12px;color:#718097}
</style>
</head>
<body>
<main>
<span class="badge">ZeaZDev · deployment pending</span>
<h1>Under Construction</h1>
<p><strong>${host}</strong> belongs to a ZeaZDev project, but its production runtime is not currently marked online. The hostname is being held safely instead of exposing an origin error or an unfinished deployment.</p>
<div class="repo"><strong>Repository</strong><a href="${repoUrl}" rel="noreferrer">cvsz/${repoName}</a></div>
<footer>HTTP 503 · Temporary maintenance response · Retry later</footer>
</main>
</body>
</html>`;
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === '/.well-known/zeaz-status' || url.pathname === '/health') {
      return Response.json({
        status: 'under-construction',
        hostname: url.hostname,
        repository: `cvsz/${repoForHost(url.hostname)}`,
      }, { status: 200, headers: { 'Cache-Control': 'no-store' } });
    }

    const repo = repoForHost(url.hostname);
    return new Response(page(url.hostname, repo), {
      status: 503,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store, max-age=0',
        'Retry-After': '900',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer',
        'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
      },
    });
  },
};
