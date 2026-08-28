const canvas = document.querySelector('#humanoid-canvas');
const stage = document.querySelector('.orb-zone');
const statusNode = document.querySelector('#status');

if (canvas && stage) {
  const ctx = canvas.getContext('2d', { alpha: true, desynchronized: true });
  const reducedMotion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  const mobile = globalThis.matchMedia?.('(max-width: 760px)').matches ?? false;
  const pointBudget = reducedMotion ? 900 : mobile ? 1700 : 3300;
  const points = [];
  const stars = [];
  const pointer = { x: 0, y: 0, active: false };
  const state = {
    mode: 'idle',
    targetEnergy: 0.08,
    energy: 0.08,
    rotation: -0.48,
    tilt: -0.05,
    time: 0,
  };

  const TAU = Math.PI * 2;
  const random = (min, max) => min + Math.random() * (max - min);

  function addPoint(x, y, z, kind = 'skin', intensity = 1) {
    points.push({
      x,
      y,
      z,
      kind,
      intensity,
      seed: Math.random() * 1000,
      size: random(0.55, 1.7),
    });
  }

  function sampleHead() {
    const headCount = Math.floor(pointBudget * 0.68);
    for (let i = 0; i < headCount; i += 1) {
      const u = Math.random();
      const v = Math.random();
      const theta = TAU * u;
      const phi = Math.acos(1 - 2 * v);
      const sinPhi = Math.sin(phi);
      let x = 0.76 * sinPhi * Math.cos(theta);
      let y = 1.02 * Math.cos(phi) + 0.28;
      let z = 0.72 * sinPhi * Math.sin(theta);

      if (y < 0.15) x *= 0.78 + Math.max(0, y + 0.65) * 0.16;
      if (x < -0.35) x *= 0.94;
      if (y > 0.6) z *= 1.04;
      if (x > 0.3) {
        const plane = 0.62 - Math.max(0, 0.45 - Math.abs(y - 0.2)) * 0.18;
        z *= plane;
      }
      addPoint(x, y, z, 'skin', random(0.6, 1));
    }

    const noseCount = Math.floor(pointBudget * 0.055);
    for (let i = 0; i < noseCount; i += 1) {
      const t = Math.random();
      const ring = Math.random() * TAU;
      addPoint(
        0.7 + t * 0.22,
        0.36 - t * 0.28 + Math.sin(ring) * 0.045,
        Math.cos(ring) * 0.065 * (0.4 + t * 0.6),
        'face',
        random(0.82, 1.2),
      );
    }

    const jawCount = Math.floor(pointBudget * 0.07);
    for (let i = 0; i < jawCount; i += 1) {
      const t = Math.random();
      addPoint(
        0.66 - t * 0.9,
        -0.18 - Math.sin(t * Math.PI) * 0.28 + random(-0.035, 0.035),
        random(-0.11, 0.11),
        'edge',
        random(0.9, 1.4),
      );
    }

    const eyeCount = Math.floor(pointBudget * 0.045);
    for (let i = 0; i < eyeCount; i += 1) {
      const a = Math.random() * TAU;
      const r = random(0.035, 0.15);
      addPoint(
        0.58 + Math.cos(a) * r,
        0.34 + Math.sin(a) * r * 0.72,
        random(-0.04, 0.04),
        'eye',
        random(1.1, 1.7),
      );
    }
  }

  function sampleNeckAndShoulders() {
    const neckCount = Math.floor(pointBudget * 0.09);
    for (let i = 0; i < neckCount; i += 1) {
      const a = Math.random() * TAU;
      const t = Math.random();
      const radius = 0.28 + t * 0.12;
      addPoint(
        -0.12 + Math.cos(a) * radius,
        -0.5 - t * 0.72,
        Math.sin(a) * radius * 0.8,
        'neck',
        random(0.65, 1.05),
      );
    }

    const shoulderCount = Math.floor(pointBudget * 0.1);
    for (let i = 0; i < shoulderCount; i += 1) {
      const t = Math.random();
      const side = Math.random() < 0.58 ? -1 : 1;
      addPoint(
        -0.12 + side * (0.18 + t * 1.3),
        -1.18 - Math.pow(t, 1.6) * 0.18 + random(-0.045, 0.045),
        random(-0.3, 0.3) * (1 - t * 0.55),
        'shoulder',
        random(0.55, 0.95),
      );
    }
  }

  function buildStars() {
    const count = mobile ? 90 : 170;
    for (let i = 0; i < count; i += 1) {
      stars.push({
        x: Math.random(),
        y: Math.random(),
        z: random(0.2, 1),
        phase: Math.random() * TAU,
      });
    }
  }

  sampleHead();
  sampleNeckAndShoulders();
  buildStars();

  function classifyStatus(text) {
    const value = String(text || '').toLowerCase();
    if (value.includes('listening') || value.includes('ฟัง')) return 'listening';
    if (value.includes('transcrib') || value.includes('ถอด') || value.includes('ประมวลเสียง')) return 'transcribing';
    if (value.includes('reason') || value.includes('think') || value.includes('คิด')) return 'thinking';
    if (value.includes('speak') || value.includes('พูด')) return 'speaking';
    if (value.includes('error') || value.includes('fail') || value.includes('ผิดพลาด')) return 'error';
    if (value.includes('connect') || value.includes('พร้อม')) return 'ready';
    return 'idle';
  }

  function applyMode(mode) {
    state.mode = mode;
    state.targetEnergy = {
      idle: 0.08,
      ready: 0.11,
      listening: 0.34,
      transcribing: 0.2,
      thinking: 0.27,
      speaking: 0.4,
      error: 0.18,
    }[mode] ?? 0.1;
    document.body.dataset.humanoidState = mode;
  }

  if (statusNode) {
    applyMode(classifyStatus(statusNode.textContent));
    new MutationObserver(() => applyMode(classifyStatus(statusNode.textContent)))
      .observe(statusNode, { childList: true, characterData: true, subtree: true });
  }

  const transcriptNode = document.querySelector('#transcript');
  if (transcriptNode) {
    new MutationObserver((records) => {
      const assistantAdded = records.some((record) => [...record.addedNodes].some(
        (node) => node instanceof HTMLElement && node.dataset?.role === 'assistant',
      ));
      if (!assistantAdded) return;
      applyMode('speaking');
      globalThis.setTimeout(() => {
        if (state.mode === 'speaking') applyMode(classifyStatus(statusNode?.textContent));
      }, reducedMotion ? 900 : 2400);
    }).observe(transcriptNode, { childList: true });
  }

  stage.addEventListener('pointermove', (event) => {
    const rect = stage.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
    pointer.y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
    pointer.active = true;
  });
  stage.addEventListener('pointerleave', () => { pointer.active = false; });

  function resize() {
    const rect = stage.getBoundingClientRect();
    const dpr = Math.min(2, globalThis.devicePixelRatio || 1);
    canvas.width = Math.max(1, Math.round(rect.width * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  new ResizeObserver(resize).observe(stage);
  resize();

  function rotatePoint(point, yaw, pitch) {
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const cosX = Math.cos(pitch);
    const sinX = Math.sin(pitch);
    const x1 = point.x * cosY - point.z * sinY;
    const z1 = point.x * sinY + point.z * cosY;
    return {
      x: x1,
      y: point.y * cosX - z1 * sinX,
      z: point.y * sinX + z1 * cosX,
    };
  }

  function pointColor(point, depth, pulse) {
    if (state.mode === 'error') return `rgba(255,108,94,${0.3 + depth * 0.5})`;
    if (point.kind === 'eye') return `rgba(202,248,255,${0.72 + pulse * 0.25})`;
    if (point.kind === 'edge' || point.kind === 'face') return `rgba(116,229,255,${0.3 + depth * 0.62})`;
    if (point.x > 0.44) return `rgba(206,197,149,${0.12 + depth * 0.4})`;
    return `rgba(42,197,255,${0.12 + depth * 0.55})`;
  }

  function drawBackground(width, height, time) {
    ctx.clearRect(0, 0, width, height);
    const cx = width * 0.5;
    const cy = height * 0.52;
    const halo = ctx.createRadialGradient(cx, cy, 10, cx, cy, Math.max(width, height) * 0.48);
    halo.addColorStop(0, 'rgba(0,154,255,0.08)');
    halo.addColorStop(0.45, 'rgba(0,74,120,0.025)');
    halo.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, width, height);

    for (const star of stars) {
      const twinkle = 0.2 + (Math.sin(time * 0.9 + star.phase) + 1) * 0.18;
      ctx.fillStyle = `rgba(73,200,255,${twinkle * star.z})`;
      const size = 0.35 + star.z * 0.75;
      ctx.fillRect(star.x * width, star.y * height, size, size);
    }

    ctx.save();
    ctx.strokeStyle = `rgba(34,185,255,${0.08 + state.energy * 0.08})`;
    ctx.lineWidth = 1;
    const ringBase = Math.min(width, height) * 0.16;
    for (let ring = 0; ring < 4; ring += 1) {
      const r = ringBase * (1 + ring * 0.32) + Math.sin(time * 1.4 + ring) * 2;
      ctx.beginPath();
      ctx.ellipse(cx, height * 0.8, r * 1.35, r * 0.35, 0, Math.PI, TAU);
      ctx.stroke();
    }
    ctx.restore();
  }

  function render(now) {
    const rect = stage.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    if (!width || !height) {
      requestAnimationFrame(render);
      return;
    }

    const dt = Math.min(0.04, Math.max(0.001, (now - (state.lastNow || now)) / 1000));
    state.lastNow = now;
    state.time += dt;
    state.energy += (state.targetEnergy - state.energy) * Math.min(1, dt * 5.4);

    const autoYaw = -0.54 + Math.sin(state.time * (state.mode === 'thinking' ? 0.6 : 0.18)) * 0.08;
    const autoPitch = -0.04 + Math.sin(state.time * 0.23) * 0.025;
    const targetYaw = autoYaw + (pointer.active ? pointer.x * 0.16 : 0);
    const targetPitch = autoPitch + (pointer.active ? pointer.y * -0.09 : 0);
    state.rotation += (targetYaw - state.rotation) * Math.min(1, dt * 3.2);
    state.tilt += (targetPitch - state.tilt) * Math.min(1, dt * 3.2);

    drawBackground(width, height, state.time);

    const cx = width * 0.5;
    const cy = height * (mobile ? 0.54 : 0.52);
    const scale = Math.min(width, height) * (mobile ? 0.31 : 0.34);
    const pulse = (Math.sin(state.time * (state.mode === 'speaking' ? 5.2 : 2.1)) + 1) * 0.5;
    const jitter = reducedMotion ? 0 : state.energy * (state.mode === 'thinking' ? 0.02 : 0.011);
    const projected = [];

    for (const point of points) {
      const wobble = Math.sin(state.time * 1.7 + point.seed) * jitter;
      const rotated = rotatePoint(
        { x: point.x + wobble, y: point.y, z: point.z + wobble * 0.4 },
        state.rotation,
        state.tilt,
      );
      const depth = Math.max(0.05, Math.min(1, (rotated.z + 1.55) / 3.1));
      const perspective = 1 / (1.8 - rotated.z * 0.22);
      projected.push({
        point,
        depth,
        x: cx + rotated.x * scale * perspective,
        y: cy - rotated.y * scale * perspective,
        size: point.size * (0.55 + depth * 0.95) * (1 + state.energy * 0.28),
      });
    }

    projected.sort((a, b) => a.depth - b.depth);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.shadowBlur = 7 + state.energy * 12;
    ctx.shadowColor = state.mode === 'error' ? 'rgba(255,78,62,0.5)' : 'rgba(0,188,255,0.48)';
    for (const item of projected) {
      ctx.fillStyle = pointColor(item.point, item.depth, pulse);
      ctx.beginPath();
      ctx.arc(item.x, item.y, item.size, 0, TAU);
      ctx.fill();
    }
    ctx.restore();

    const coreY = cy + scale * 0.68;
    const coreRadius = 10 + state.energy * 26 + pulse * 4;
    const core = ctx.createRadialGradient(cx - scale * 0.05, coreY, 0, cx - scale * 0.05, coreY, coreRadius * 2.8);
    core.addColorStop(0, 'rgba(218,252,255,0.98)');
    core.addColorStop(0.12, 'rgba(68,218,255,0.92)');
    core.addColorStop(0.45, 'rgba(0,130,255,0.38)');
    core.addColorStop(1, 'rgba(0,90,255,0)');
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(cx - scale * 0.05, coreY, coreRadius * 2.8, 0, TAU);
    ctx.fill();

    requestAnimationFrame(render);
  }

  requestAnimationFrame(render);
}
