"""
zc_chrome.py — CLI browsing-agent loop (zAICoder in Chrome analog)
AI Model Coder CLI v1.15.0

IMPORTANT — what this module is, and isn't: zAICoder in Chrome is a browser
extension with a side panel, click/type/tab control, logged-in-session
context, and its own prompt-injection defenses — none of which a CLI
process can replicate, because a terminal has no browser to sit inside.
This module is a same-*shape* analog for headless use: zAICoder reads a
page's text, decides one action, this module performs it (fetch a URL,
or stop and report), and the loop repeats with the new page as context.
There's no clicking, no form-filling, no logged-in cookies, and no
Chrome-specific attack surface — just fetch-observe-decide, in a loop.

If you actually want zAICoder in Chrome, install the extension from the
Chrome Web Store and sign in with your zAICoder account; there's no API
that lets a script drive it. This module exists for headless/CI use
cases (e.g. "does this doc site mention X, and if so what does the
linked page say") where a real browser isn't available or wanted.

Safety note (read before pointing this at untrusted sites): browsing
agents are exposed to prompt injection — instructions hidden in page
content that try to redirect the agent. This module has none of the
classifier-based defenses zAICoder in Chrome ships with. Don't run it
unattended against sites you don't control, and don't feed its output
back into anything that can take real-world actions (payments, emails,
credential changes) without a human checking first.

Requires: nothing beyond the stdlib (urllib) for fetching; a very small,
dependency-free HTML-to-text step is used for extraction (see _strip_html)
rather than pulling in a parser — good enough for reading text, not for
sites that render content via JavaScript.

CLI:
  --browse URL              Start a browsing-agent session at URL
  --browse-task TEXT         What to do/find (required with --browse)
  --browse-max-steps N       Max fetch/decide iterations (default 6)
  --browse-allow-domain D     Restrict navigation to this domain (repeatable)
"""
import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from wire.exceptions import APIError
from wire.resilience import raise_for_http_error, retry

MAX_PAGE_CHARS = 8000  # keep pages small enough to stay a cheap loop step


class _TextExtractor(HTMLParser):
    """Minimal HTML→text: strips tags/script/style, keeps <a href> as [text](url)."""

    def __init__(self):
        super().__init__()
        self.chunks = []
        self.links = []
        self._skip = 0
        self._current_href = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._current_href = href

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip > 0:
            self._skip -= 1
        if tag == "a":
            self._current_href = None

    def handle_data(self, data):
        if self._skip:
            return
        text = data.strip()
        if not text:
            return
        if self._current_href:
            self.links.append((text, self._current_href))
            self.chunks.append(f"[{text}]({self._current_href})")
        else:
            self.chunks.append(text)

    def text(self):
        return " ".join(self.chunks)[:MAX_PAGE_CHARS]


def fetch_page(url, timeout=15):
    """Fetch a URL and return (text, links, error). Never raises."""
    try:
        raw = _fetch_retrying(url, timeout)
    except APIError as e:
        return None, [], f"HTTP {e.status_code} fetching {url}"
    except Exception as e:
        return None, [], f"{type(e).__name__} fetching {url}"

    extractor = _TextExtractor()
    try:
        extractor.feed(raw)
    except Exception as e:
        return None, [], f"parse error on {url}: {e}"
    return extractor.text(), extractor.links, None


# No CircuitBreaker here deliberately: each step of a browsing session can
# navigate to a completely different, unrelated site — a shared breaker
# would trip on one dead page and start short-circuiting fetches to sites
# that are otherwise reachable.
@retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
def _fetch_retrying(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (wire-browse)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
        # Translates to the AICoderError hierarchy so retry() above can tell
        # a transient failure from a permanent one; fetch_page()'s `except
        # Exception` below still catches whatever this raises either way.
        raise_for_http_error(e)


def _domain_allowed(url, allowed_domains):
    if not allowed_domains:
        return True
    host = urlparse(url).netloc.lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in allowed_domains)


SYSTEM_PROMPT = """\
You are a headless browsing agent embedded in a CLI tool. Each turn you \
are given the current page's URL, its extracted text (including links as \
[text](url)), and a task. Decide the single next action.

Respond with ONLY a JSON object, no other text, in one of these shapes:

  {"action": "navigate", "url": "https://...", "reason": "why"}
  {"action": "answer", "text": "final answer to the task"}

Use "navigate" to follow a link relevant to the task (resolve relative \
links against the current page yourself if given one). Use "answer" as \
soon as you can complete the task from what you've seen — don't navigate \
more than necessary. If you get stuck (broken links, irrelevant content, \
paywall), use "answer" and say so plainly rather than guessing.
"""


def cmd_browse(api_key, model, start_url, task, max_steps=6, allowed_domains=None,
               temperature=0.0, max_tokens=1024):
    from wire.coder import Coder

    c = Coder(api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)
    print(f"\033[94mAI Model Coder — browse\033[0m  (model: {c.model})")
    print(f"Task: {task}")
    print(f"Start: {start_url}\n")

    url = start_url
    visited = set()
    for step in range(1, max_steps + 1):
        if url in visited:
            print(f"\033[93m[loop detected] already visited {url}; stopping.\033[0m")
            break
        if not _domain_allowed(url, allowed_domains):
            print(f"\033[91m[blocked] {url} is outside --browse-allow-domain restriction.\033[0m")
            break
        visited.add(url)

        print(f"\033[96m[{step}/{max_steps}] fetching\033[0m {url}")
        text, links, error = fetch_page(url)
        if error:
            print(f"\033[91m[fetch error] {error}\033[0m")
            break

        prompt = (
            f"Task: {task}\n\nCurrent URL: {url}\n\n"
            f"Page text (truncated to {MAX_PAGE_CHARS} chars):\n{text}"
        )
        reply = c.generate(prompt, system=SYSTEM_PROMPT, history=[])

        decision = _parse_json_action(reply)
        if decision is None:
            print(f"\033[93m[unparsable response, treating as final answer]\033[0m\n{reply}")
            return reply

        if decision["action"] == "answer":
            answer = decision.get("text", "")
            print(f"\n\033[92mzc›\033[0m {answer}")
            return answer

        if decision["action"] == "navigate":
            next_url = urljoin(url, decision.get("url", ""))
            print(f"  \033[90m→ navigating: {decision.get('reason', '')}\033[0m")
            url = next_url
            continue

        print(f"\033[93m[unknown action {decision.get('action')!r}, stopping]\033[0m")
        break

    print("\033[93m[max steps reached without a final answer]\033[0m")
    return None


def _parse_json_action(reply):
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if data.get("action") not in ("navigate", "answer"):
        return None
    return data
