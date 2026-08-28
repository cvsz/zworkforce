import assert from "node:assert/strict";
import test from "node:test";

import { isSafeMarkdownUrl, renderMarkdownFragment, tokenizeMarkdown } from "../public/markdown.mjs";

function createNode(tagName) {
  return {
    tagName,
    children: [],
    textContent: "",
    className: "",
    href: "",
    rel: "",
    target: "",
    appendChild(node) {
      this.children.push(node);
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [...nodes];
    },
  };
}

function createDocument() {
  return {
    createDocumentFragment() {
      return createNode("#fragment");
    },
    createElement(tagName) {
      return createNode(tagName);
    },
    createTextNode(text) {
      return { nodeType: 3, textContent: text };
    },
  };
}

test("tokenizeMarkdown recognizes headings, lists, quotes, and code fences", () => {
  const blocks = tokenizeMarkdown(`# Title\n\n- First\n- Second\n\n> Quote line\n> Another line\n\n\`\`\`js\nconsole.log('hi')\n\`\`\`\n\nParagraph line`);

  assert.deepEqual(blocks, [
    { type: "heading", level: 1, text: "Title" },
    { type: "list", items: ["First", "Second"] },
    { type: "quote", text: "Quote line\nAnother line" },
    { type: "code", language: "js", text: "console.log('hi')" },
    { type: "paragraph", text: "Paragraph line" },
  ]);
});

test("safe markdown urls only allow http and https", () => {
  assert.equal(isSafeMarkdownUrl("https://example.com"), true);
  assert.equal(isSafeMarkdownUrl("http://example.com/path"), true);
  assert.equal(isSafeMarkdownUrl("javascript:alert(1)"), false);
  assert.equal(isSafeMarkdownUrl("data:text/html,<script>alert(1)</script>"), false);
});

test("renderMarkdownFragment keeps raw html as text and renders safe links", () => {
  const documentLike = createDocument();
  const fragment = renderMarkdownFragment(
    documentLike,
    "See [Docs](https://example.com) and </style><script>alert(1)</script>\n\n```js\nconsole.log('safe')\n```",
  );

  assert.equal(fragment.children.length, 2);
  const paragraph = fragment.children[0];
  assert.equal(paragraph.tagName, "p");
  assert.equal(paragraph.children[0].textContent, "See ");
  assert.equal(paragraph.children[1].tagName, "a");
  assert.equal(paragraph.children[1].href, "https://example.com");
  assert.equal(paragraph.children[2].textContent, " and </style><script>alert(1)</script>");

  const codeBlock = fragment.children[1];
  assert.equal(codeBlock.tagName, "pre");
  assert.equal(codeBlock.children[0].tagName, "code");
  assert.equal(codeBlock.children[0].textContent, "console.log('safe')");
});
