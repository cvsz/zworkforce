const liveUrl = process.env.ZTTSHOP_LIVE_URL?.trim();
const timeoutMs = Number.parseInt(process.env.LIVE_SMOKE_TIMEOUT_MS ?? "15000", 10);

if (!liveUrl) {
  console.error("ZTTSHOP_LIVE_URL is required");
  process.exit(1);
}

let baseUrl;
try {
  baseUrl = new URL(liveUrl);
  if (!["http:", "https:"].includes(baseUrl.protocol)) {
    throw new Error("must use http:// or https://");
  }
} catch (error) {
  console.error("ZTTSHOP_LIVE_URL must be an absolute HTTP(S) URL: " + error.message);
  process.exit(1);
}

if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
  console.error("LIVE_SMOKE_TIMEOUT_MS must be a positive integer");
  process.exit(1);
}

const checks = [
  { path: "/", statuses: [307, 308], location: "/en" },
  { path: "/en", statuses: [200], lang: "en", title: "zTTShop — TikTok Shop API Client for PHP" },
  { path: "/th", statuses: [200], lang: "th", title: "zTTShop — PHP SDK สำหรับ TikTok Shop API" },
  { path: "/en/privacy", statuses: [200], lang: "en", title: "Privacy Policy — zTTShop" },
  { path: "/th/privacy", statuses: [200], lang: "th", title: "นโยบายความเป็นส่วนตัว — zTTShop" },
  { path: "/en/terms", statuses: [200], lang: "en", title: "Terms of Use — zTTShop" },
  { path: "/th/terms", statuses: [200], lang: "th", title: "ข้อกำหนดการใช้งาน — zTTShop" },
];

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function checkRoute(check) {
  const url = new URL(check.path, baseUrl);
  const response = await fetch(url, {
    redirect: "manual",
    headers: { accept: "text/html" },
    signal: AbortSignal.timeout(timeoutMs),
  });
  const body = await response.text();

  assert(check.statuses.includes(response.status), "expected " + check.statuses.join("/") + " but got " + response.status);
  if (check.statuses.includes(200)) {
    assert(
      response.headers.get("content-type")?.toLowerCase().includes("text/html"),
      "response was not HTML",
    );
  }

  if (check.location) {
    const location = response.headers.get("location");
    assert(location, "redirect did not include a Location header");
    assert(new URL(location, url).pathname === check.location, "expected redirect to " + check.location + " but got " + location);
  }

  if (check.lang) {
    const htmlLang = body.match(/<html[^>]*\blang=["']([^"']+)["']/i)?.[1];
    assert(htmlLang === check.lang, "expected html lang=" + check.lang + " but got " + (htmlLang ?? "missing"));
  }

  if (check.title) {
    assert(body.includes("<title>" + check.title + "</title>"), "missing title: " + check.title);
  }

  return check.path + " (" + response.status + ")";
}

const failures = [];
for (const check of checks) {
  try {
    const result = await checkRoute(check);
    console.log("PASS " + result);
  } catch (error) {
    failures.push(check.path + ": " + error.message);
    console.error("FAIL " + check.path + ": " + error.message);
  }
}

if (failures.length > 0) {
  console.error("Live site smoke checks failed (" + failures.length + "/" + checks.length + ").");
  process.exit(1);
}

console.log("Live site smoke checks passed (" + checks.length + "/" + checks.length + ").");
