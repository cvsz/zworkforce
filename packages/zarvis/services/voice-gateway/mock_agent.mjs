import { createServer } from "node:http";
import { createHash } from "node:crypto";

const port = Number(process.env.VOICE_AGENT_PORT || 8766);
const GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

function encodeFrame(text) {
  const payload = Buffer.from(text, "utf8");
  const length = payload.length;
  let header;
  if (length < 126) {
    header = Buffer.from([0x81, length]);
  } else if (length <= 65535) {
    header = Buffer.alloc(4);
    header[0] = 0x81;
    header[1] = 126;
    header.writeUInt16BE(length, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x81;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(length), 2);
  }
  return Buffer.concat([header, payload]);
}

function decodeFrames(buffer) {
  const messages = [];
  let offset = 0;
  while (offset + 2 <= buffer.length) {
    const b1 = buffer[offset];
    const b2 = buffer[offset + 1];
    const opcode = b1 & 0x0f;
    const isMasked = (b2 & 0x80) !== 0;
    let payloadLen = b2 & 0x7f;
    let headerLen = 2;

    if (payloadLen === 126) {
      if (offset + 4 > buffer.length) break;
      payloadLen = buffer.readUInt16BE(offset + 2);
      headerLen = 4;
    } else if (payloadLen === 127) {
      if (offset + 10 > buffer.length) break;
      payloadLen = Number(buffer.readBigUInt64BE(offset + 2));
      headerLen = 10;
    }

    const maskLen = isMasked ? 4 : 0;
    if (offset + headerLen + maskLen + payloadLen > buffer.length) break;

    let mask = null;
    if (isMasked) {
      mask = buffer.subarray(offset + headerLen, offset + headerLen + 4);
    }
    const rawData = buffer.subarray(offset + headerLen + maskLen, offset + headerLen + maskLen + payloadLen);
    const unmasked = Buffer.alloc(payloadLen);
    for (let i = 0; i < payloadLen; i++) {
      unmasked[i] = isMasked ? (rawData[i] ^ mask[i % 4]) : rawData[i];
    }

    if (opcode === 0x01) { // text
      messages.push(unmasked.toString("utf8"));
    } else if (opcode === 0x08) { // close
      messages.push({ type: "close" });
    }

    offset += headerLen + maskLen + payloadLen;
  }
  return { messages, remaining: buffer.subarray(offset) };
}

const server = createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ status: "ok", service: "voice-agent-mock" }));
  }
  res.writeHead(404);
  res.end();
});

server.on("upgrade", (req, socket, head) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) {
    socket.destroy();
    return;
  }
  const accept = createHash("sha1").update(key + GUID).digest("base64");
  const protocol = req.headers["sec-websocket-protocol"] || "";
  const headerLines = [
    "HTTP/1.1 101 Switching Protocols",
    "Upgrade: websocket",
    "Connection: Upgrade",
    `Sec-WebSocket-Accept: ${accept}`
  ];
  if (protocol) {
    headerLines.push(`Sec-WebSocket-Protocol: ${protocol.split(",")[0].trim()}`);
  }
  headerLines.push("", "");

  socket.write(headerLines.join("\r\n"));

  // Send initial session.created event
  socket.write(encodeFrame(JSON.stringify({
    type: "session.created",
    session: { id: "sess_" + Date.now(), model: "qwen3:8b" }
  })));

  let buffer = Buffer.alloc(0);

  socket.on("data", (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    const { messages, remaining } = decodeFrames(buffer);
    buffer = remaining;

    for (const msg of messages) {
      if (typeof msg === "string") {
        try {
          const parsed = JSON.parse(msg);
          if (parsed.type === "session.update") {
            socket.write(encodeFrame(JSON.stringify({
              type: "session.updated",
              session: parsed.session
            })));
          } else if (parsed.type === "input_audio_buffer.append") {
            // Echo speech feedback
          }
        } catch (e) {}
      } else if (msg?.type === "close") {
        socket.end();
      }
    }
  });
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Standalone Mock Voice Agent listening on http://127.0.0.1:${port}`);
});
