function normalizeText(text) {
  return String(text ?? "").replace(/\r\n/g, "\n");
}

function tokenizeInline(text) {
  const input = normalizeText(text);
  const tokens = [];
  const pattern = /(`[^`]+`|\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)/g;

  let lastIndex = 0;
  for (let match = pattern.exec(input); match; match = pattern.exec(input)) {
    if (match.index > lastIndex) {
      tokens.push({ type: "text", value: input.slice(lastIndex, match.index) });
    }
    const value = match[0];
    if (value.startsWith("`")) {
      tokens.push({ type: "code", value: value.slice(1, -1) });
    } else if (value.startsWith("[")) {
      const linkMatch = value.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      tokens.push({
        type: "link",
        label: linkMatch ? linkMatch[1] : value,
        url: linkMatch ? linkMatch[2] : "",
      });
    } else if (value.startsWith("**") || value.startsWith("__")) {
      tokens.push({ type: "strong", value: value.slice(2, -2) });
    } else if (value.startsWith("*") || value.startsWith("_")) {
      tokens.push({ type: "em", value: value.slice(1, -1) });
    }
    lastIndex = match.index + value.length;
  }

  if (lastIndex < input.length) {
    tokens.push({ type: "text", value: input.slice(lastIndex) });
  }

  return tokens;
}

export function isSafeMarkdownUrl(url) {
  try {
    const parsed = new URL(url, "https://zchat.local/");
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function tokenizeMarkdown(text) {
  const lines = normalizeText(text).split("\n");
  const blocks = [];
  let paragraph = [];

  function flushParagraph() {
    if (!paragraph.length) return;
    blocks.push({ type: "paragraph", text: paragraph.join("\n") });
    paragraph = [];
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim()) {
      flushParagraph();
      continue;
    }

    const codeFence = line.match(/^```([\w-]+)?\s*$/);
    if (codeFence) {
      flushParagraph();
      const language = codeFence[1] || "";
      const codeLines = [];
      index += 1;
      while (index < lines.length && !/^```\s*$/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: "code", language, text: codeLines.join("\n") });
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2] });
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      flushParagraph();
      const items = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*]\s+/, ""));
        index += 1;
      }
      index -= 1;
      blocks.push({ type: "list", items });
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      flushParagraph();
      const quoteLines = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      index -= 1;
      blocks.push({ type: "quote", text: quoteLines.join("\n") });
      continue;
    }

    paragraph.push(line);
  }

  flushParagraph();
  return blocks;
}

function appendInline(documentLike, parent, text) {
  for (const token of tokenizeInline(text)) {
    if (token.type === "text") {
      parent.appendChild(documentLike.createTextNode(token.value));
      continue;
    }

    if (token.type === "code") {
      const code = documentLike.createElement("code");
      code.textContent = token.value;
      parent.appendChild(code);
      continue;
    }

    if (token.type === "strong" || token.type === "em") {
      const element = documentLike.createElement(token.type === "strong" ? "strong" : "em");
      element.textContent = token.value;
      parent.appendChild(element);
      continue;
    }

    if (token.type === "link") {
      if (isSafeMarkdownUrl(token.url)) {
        const link = documentLike.createElement("a");
        link.textContent = token.label;
        link.href = token.url;
        link.rel = "noreferrer noopener";
        link.target = "_blank";
        parent.appendChild(link);
      } else {
        parent.appendChild(documentLike.createTextNode(token.label));
      }
    }
  }
}

export function renderMarkdownFragment(documentLike, text) {
  const fragment = documentLike.createDocumentFragment();
  for (const block of tokenizeMarkdown(text)) {
    if (block.type === "paragraph") {
      const paragraph = documentLike.createElement("p");
      block.text.split("\n").forEach((line, index) => {
        if (index > 0) {
          paragraph.appendChild(documentLike.createElement("br"));
        }
        appendInline(documentLike, paragraph, line);
      });
      fragment.appendChild(paragraph);
      continue;
    }

    if (block.type === "heading") {
      const heading = documentLike.createElement(`h${block.level}`);
      appendInline(documentLike, heading, block.text);
      fragment.appendChild(heading);
      continue;
    }

    if (block.type === "code") {
      const pre = documentLike.createElement("pre");
      const code = documentLike.createElement("code");
      if (block.language) {
        code.className = `language-${block.language}`;
      }
      code.textContent = block.text;
      pre.appendChild(code);
      fragment.appendChild(pre);
      continue;
    }

    if (block.type === "list") {
      const list = documentLike.createElement("ul");
      for (const itemText of block.items) {
        const item = documentLike.createElement("li");
        appendInline(documentLike, item, itemText);
        list.appendChild(item);
      }
      fragment.appendChild(list);
      continue;
    }

    if (block.type === "quote") {
      const quote = documentLike.createElement("blockquote");
      quote.textContent = block.text;
      fragment.appendChild(quote);
    }
  }
  return fragment;
}
