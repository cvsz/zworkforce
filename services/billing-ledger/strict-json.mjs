// Reject ambiguous JSON member names before consuming security-sensitive JWTs.
// JSON.parse alone accepts duplicate names and silently keeps the last value.
export function parseJsonRejectingDuplicateKeys(source) {
  const parsed = JSON.parse(source); // Enforce the full JSON grammar first.
  let offset = 0;
  const skipSpace = () => {
    while (offset < source.length && /[\x20\t\r\n]/.test(source[offset])) offset++;
  };
  const scanString = () => {
    if (source[offset] !== '"') throw new SyntaxError('Expected JSON string');
    const start = offset++;
    while (offset < source.length) {
      if (source[offset] === '\\') { offset += 2; continue; }
      if (source[offset++] === '"') return JSON.parse(source.slice(start, offset));
    }
    throw new SyntaxError('Unterminated JSON string');
  };
  const scanValue = depth => {
    if (depth > 64) throw new SyntaxError('JSON nesting exceeds security limit');
    skipSpace();
    if (source[offset] === '{') {
      offset++;
      skipSpace();
      const names = new Set();
      while (source[offset] !== '}') {
        const name = scanString();
        if (names.has(name)) throw new SyntaxError('Duplicate JSON member name');
        names.add(name);
        skipSpace();
        if (source[offset++] !== ':') throw new SyntaxError('Expected JSON colon');
        scanValue(depth + 1);
        skipSpace();
        if (source[offset] !== ',') break;
        offset++;
        skipSpace();
      }
      if (source[offset++] !== '}') throw new SyntaxError('Expected JSON object end');
    } else if (source[offset] === '[') {
      offset++;
      skipSpace();
      while (source[offset] !== ']') {
        scanValue(depth + 1);
        skipSpace();
        if (source[offset] !== ',') break;
        offset++;
        skipSpace();
      }
      if (source[offset++] !== ']') throw new SyntaxError('Expected JSON array end');
    } else if (source[offset] === '"') {
      scanString();
    } else {
      const start = offset;
      while (offset < source.length && !/[\x20\t\r\n,}\]]/.test(source[offset])) offset++;
      if (offset === start) throw new SyntaxError('Expected JSON value');
    }
  };
  scanValue(0);
  skipSpace();
  if (offset !== source.length) throw new SyntaxError('Unexpected JSON suffix');
  return parsed;
}
