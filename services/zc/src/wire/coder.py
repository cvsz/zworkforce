"""
coder.py — zAICoder API integration core
AI Model Coder CLI v1.7.0
"""
import json
import os
import urllib.error
import urllib.request

from wire.config import Config
from wire.exceptions import APIError, AuthenticationError, RateLimitError, TransientAPIError
from wire.logging_config import get_logger
from wire.resilience import CircuitBreaker, retry
from wire.utils import sampling_kwargs

logger = get_logger("coder")

# Shared across Coder instances within a process so repeated failures
# (e.g. an outage during a long --agent-orchestrate run) trip the breaker
# once rather than per-instance, instead of each Coder() call starting
# with a fresh "closed" breaker that never actually protects anything.
_default_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class Coder:
    def __init__(self, api_key=None, model=None, temperature=0.3, max_tokens=4096,
                 provider=None, personality_style=None,
                 service_tier=None, inference_geo=None, fast_mode=False):
        self.config = Config()
        self.api_key = api_key or self.config.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
        _m = model or self.config.get("model") or "claude-sonnet-5"
        self.model = _m.replace("\n", "").replace("\r", "")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.provider = provider or "anthropic"
        self.personality_style = personality_style
        # service_tier: "auto" (use Priority Tier if committed, else fall
        # back to standard) or "standard_only". Not sent unless set — most
        # accounts have no Priority Tier commitment (they're no longer
        # purchasable, only existing commitments still work) and it's
        # rejected outright on Sonnet 5 / Mythos-tier models.
        self.service_tier = service_tier
        # inference_geo: "us" (US-only inference, 1.1x pricing) or "global"
        # (default). Only Opus 4.6+/Sonnet 4.6+ and later accept this param
        # at all — earlier models 400 if it's set.
        self.inference_geo = inference_geo
        # fast_mode: sends speed:"fast" — reduced-latency mode, currently a
        # research-preview feature restricted to certain Opus models and
        # billed at a premium rate. See zc_models.py FAST_MODE_SUPPORTED.
        self.fast_mode = fast_mode

    def generate(self, prompt, system=None, file_content=None, history=None):
        """Generate a response from the AI model."""
        if not self.api_key:
            logger.error("missing_api_key")
            return "[ERROR] No API key configured. Set ANTHROPIC_API_KEY or run --setup."

        logger.info("generate_start", extra={"model": self.model, "prompt_chars": len(prompt or "")})
        messages = list(history or [])

        user_content = prompt
        if file_content:
            user_content = f"File content:\n```\n{file_content}\n```\n\n{prompt}"

        if self.personality_style:
            try:
                from wire.personalities import PersonalityManager
                pm = PersonalityManager()
                addition = pm.build_prompt_addition(self.personality_style)
                if addition and system:
                    system = system + "\n\n" + addition
                elif addition:
                    system = addition
            except Exception:
                pass

        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            # Was accepted in __init__ but never sent — dead code. Now sent,
            # guarded by sampling_kwargs() since Sonnet 5/Fable 5/Mythos 5
            # 400 on any explicit sampling param.
            **sampling_kwargs(self.model, temperature=self.temperature),
        }
        if system:
            payload["system"] = system
        if self.service_tier:
            payload["service_tier"] = self.service_tier
        if self.inference_geo:
            payload["inference_geo"] = self.inference_geo
        if self.fast_mode:
            payload["speed"] = "fast"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_default_breaker)
        def _call():
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                body = e.read().decode()
                if e.code == 401:
                    raise AuthenticationError("API key rejected (401)", details={"body": body[:300]})
                if e.code == 429:
                    retry_after = None
                    try:
                        retry_after = float(e.headers.get("Retry-After", "")) if e.headers else None
                    except (TypeError, ValueError):
                        pass
                    raise RateLimitError("Rate limited (429)", retry_after=retry_after, details={"body": body[:300]})
                if e.code >= 500:
                    raise TransientAPIError(f"Server error ({e.code})", details={"body": body[:300]})
                raise APIError(f"Request rejected ({e.code})", status_code=e.code, details={"body": body[:300]})
            except (TimeoutError, ConnectionError, OSError) as e:
                # Covers socket timeouts and connection resets from urllib,
                # which surface as plain OSError/ConnectionError subclasses,
                # not HTTPError. These are transient/retryable by nature.
                raise TransientAPIError(f"Network error: {e}")

        # Sanitize model name to prevent Log Injection
        safe_model = self.model.replace('\r', '').replace('\n', '')

        try:
            data = _call()
        except AuthenticationError as e:
            logger.error("auth_failed", extra={"model": safe_model})
            return f"[API ERROR 401] {e.message}"
        except RateLimitError as e:
            logger.error("rate_limited_after_retries", extra={"model": safe_model})
            return f"[API ERROR 429] {e.message}"
        except APIError as e:
            logger.error("api_error", extra={"model": safe_model, "status_code": e.status_code})
            return f"[API ERROR {e.status_code}] {e.message}"
        except TransientAPIError as e:
            logger.error("transient_error_exhausted_retries", extra={"model": safe_model})
            return f"[ERROR] {e.message}"
        except Exception as e:
            logger.exception("unexpected_error", extra={"model": safe_model})
            return f"[ERROR] {e}"

        # Was `data["content"][0]["text"]` — broke (wrong text, or a
        # KeyError/IndexError outright) whenever content[0] wasn't a
        # plain text block: thinking-capable models (Sonnet 5, Opus
        # 4.8, Fable 5/Mythos 5 — Fable 5 has thinking on by default,
        # see zc_fable5.py) can return a thinking block first,
        # and any response with >1 text block silently dropped every
        # block after the first. Concatenate every text block instead,
        # matching the pattern already used in zc_models.py /
        # zc_fable5.py / zc_mythos5.py.
        content = data.get("content", [])
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        if not text and data.get("stop_reason") == "refusal":
            logger.info("model_refused", extra={"model": safe_model})
            return "[REFUSED] Model declined this request."
        logger.info("generate_ok", extra={"model": safe_model, "response_chars": len(text)})
        return text