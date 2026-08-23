import assert from "node:assert/strict";
import test from "node:test";

// --- 1. Mobile Menu Auto-Collapse Logic Stress Tests ---

test("Mobile Menu Auto-Collapse: anchor link click closes details menu", () => {
  // Simulate DOM structure for SiteNav mobile menu
  let detailsOpen = true;

  const mockDetails = {
    get open() { return detailsOpen; },
    set open(val) { detailsOpen = val; }
  };

  const handleMobileNavClick = (e, detailsRef) => {
    const target = e.target;
    // Simulate target.closest("a")
    if (target.closest && target.closest("a")) {
      if (detailsRef.current) {
        detailsRef.current.open = false;
      }
    }
  };

  const detailsRef = { current: mockDetails };

  // Test 1a: Click anchor element
  const anchorElement = {
    tagName: "A",
    closest: (selector) => selector === "a" ? anchorElement : null
  };

  handleMobileNavClick({ target: anchorElement }, detailsRef);
  assert.equal(detailsOpen, false, "Menu should be closed after clicking anchor link");

  // Test 1b: Click SVG child inside anchor link
  detailsOpen = true;
  const svgChildElement = {
    tagName: "SVG",
    closest: (selector) => selector === "a" ? anchorElement : null
  };

  handleMobileNavClick({ target: svgChildElement }, detailsRef);
  assert.equal(detailsOpen, false, "Menu should be closed after clicking element inside anchor link");

  // Test 1c: Click non-anchor link (e.g. background div or span)
  detailsOpen = true;
  const divElement = {
    tagName: "DIV",
    closest: (selector) => null
  };

  handleMobileNavClick({ target: divElement }, detailsRef);
  assert.equal(detailsOpen, true, "Menu should remain open when clicking non-anchor element");

  // Test 1d: Missing detailsRef.current (e.g. unmounted or null ref)
  detailsOpen = true;
  const nullDetailsRef = { current: null };

  assert.doesNotThrow(() => {
    handleMobileNavClick({ target: anchorElement }, nullDetailsRef);
  }, "Should not throw error when detailsRef.current is null");
  assert.equal(detailsOpen, true, "State unaffected when detailsRef is null");

  // Test 1e: Rapid clicks on anchor links
  detailsOpen = true;
  for (let i = 0; i < 100; i++) {
    handleMobileNavClick({ target: anchorElement }, detailsRef);
    assert.equal(detailsOpen, false);
  }
});

// --- 2. URL Location Hash Preservation Stress Tests ---

test("URL Location Hash Preservation across Language Switches", () => {
  const localizedPath = (targetLocale, pathname = "") => {
    const base = targetLocale === "en" ? "/en" : "/th";
    return pathname ? `${base}/${pathname}` : base;
  };

  const buildTargetHref = (targetLocale, pathname, currentHash) => {
    return `${localizedPath(targetLocale, pathname)}${currentHash}`;
  };

  // Test 2a: Empty hash
  assert.equal(buildTargetHref("th", "", ""), "/th");
  assert.equal(buildTargetHref("en", "privacy", ""), "/en/privacy");

  // Test 2b: Literal empty hash symbol '#'
  assert.equal(buildTargetHref("th", "", "#"), "/th#");
  assert.equal(buildTargetHref("th", "terms", "#"), "/th/terms#");

  // Test 2c: Standard anchor section hash
  assert.equal(buildTargetHref("th", "", "#workflow"), "/th#workflow");
  assert.equal(buildTargetHref("en", "", "#capabilities"), "/en#capabilities");
  assert.equal(buildTargetHref("th", "privacy", "#overview"), "/th/privacy#overview");

  // Test 2d: Encoded hash (e.g., #section%201, #%E0%B8%AB%E0%B8%A5%E0%B8%B1%E0%B8%81)
  assert.equal(buildTargetHref("th", "", "#section%201"), "/th#section%201");
  assert.equal(buildTargetHref("en", "terms", "#section%202.1"), "/en/terms#section%202.1");

  // Test 2e: Query string + hash scenario
  // When window.location has query string and hash, e.g. http://site.com/en?foo=bar#section
  // window.location.hash returns "#section"
  const mockWindowHash = "#section";
  assert.equal(buildTargetHref("th", "", mockWindowHash), "/th#section");
});

// --- 3. CopyButton Behavior Stress Tests ---

test("CopyButton behavior with Clipboard API, fallback, rapid clicks, timer", async () => {
  let clipboardWritten = null;
  let execCommandCalled = false;
  let textareaValue = null;

  // Mock global window/navigator/document environment
  const mockNavigator = {
    clipboard: {
      writeText: async (text) => {
        if (text === "FAIL_CLIPBOARD") {
          throw new Error("Clipboard API rejected");
        }
        clipboardWritten = text;
      }
    }
  };

  const createdElements = [];
  const mockDocument = {
    createElement: (tag) => {
      const el = {
        tagName: tag.toUpperCase(),
        style: {},
        value: "",
        select: () => {},
      };
      createdElements.push(el);
      return el;
    },
    body: {
      appendChild: (el) => { el.attached = true; },
      removeChild: (el) => { el.attached = false; }
    },
    execCommand: (cmd) => {
      if (cmd === "copy") {
        execCommandCalled = true;
        textareaValue = createdElements[createdElements.length - 1]?.value;
        return true;
      }
      return false;
    }
  };

  // Implementation logic from CopyButton handleCopy
  const executeCopyLogic = async (text, customNavigator = mockNavigator, customDocument = mockDocument) => {
    let copiedState = false;
    try {
      if (typeof customNavigator !== "undefined" && customNavigator.clipboard && customNavigator.clipboard.writeText) {
        await customNavigator.clipboard.writeText(text);
      } else {
        throw new Error("Clipboard API unavailable");
      }
    } catch {
      const textarea = customDocument.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      customDocument.body.appendChild(textarea);
      textarea.select();
      customDocument.execCommand("copy");
      customDocument.body.removeChild(textarea);
    }
    copiedState = true;
    return copiedState;
  };

  // Test 3a: Successful Clipboard API copy
  clipboardWritten = null;
  const result1 = await executeCopyLogic("composer require haistar/tiktokshop-api-client");
  assert.equal(result1, true);
  assert.equal(clipboardWritten, "composer require haistar/tiktokshop-api-client");

  // Test 3b: Fallback when Clipboard API rejects / fails
  execCommandCalled = false;
  textareaValue = null;
  const result2 = await executeCopyLogic("FAIL_CLIPBOARD");
  assert.equal(result2, true);
  assert.equal(execCommandCalled, true);
  assert.equal(textareaValue, "FAIL_CLIPBOARD");

  // Test 3c: Fallback when navigator.clipboard is undefined
  execCommandCalled = false;
  textareaValue = null;
  const result3 = await executeCopyLogic("NO_CLIPBOARD_API", {});
  assert.equal(result3, true);
  assert.equal(execCommandCalled, true);
  assert.equal(textareaValue, "NO_CLIPBOARD_API");

  // Test 3d: Rapid consecutive clicks
  for (let i = 0; i < 50; i++) {
    const res = await executeCopyLogic(`rapid_text_${i}`);
    assert.equal(res, true);
  }
});
