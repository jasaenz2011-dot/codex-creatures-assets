'use strict';

// ── Low-latency audio constraints ──────────────────────────────────────────
const AUDIO_CONSTRAINTS = {
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    // Keep sample rate low to reduce encode/decode time
    sampleRate: 16000,
    channelCount: 1,
    latency: 0,          // request the lowest device latency
  },
  video: false,
};

// STUN servers — multiple gives faster ICE resolution
const ICE_CONFIG = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    { urls: 'stun:stun.cloudflare.com:3478' },
  ],
  bundlePolicy: 'max-bundle',
  rtcpMuxPolicy: 'require',
  iceCandidatePoolSize: 4,   // pre-gather candidates to cut ICE time
};

// ── State ──────────────────────────────────────────────────────────────────
let socket = null;
let localStream = null;
let muted = false;
let currentRoom = null;

// peerId → { pc: RTCPeerConnection, card: HTMLElement }
const peers = new Map();

// ── DOM refs ───────────────────────────────────────────────────────────────
const joinPanel   = document.getElementById('join-panel');
const roomPanel   = document.getElementById('room-panel');
const roomInput   = document.getElementById('room-input');
const joinBtn     = document.getElementById('join-btn');
const leaveBtn    = document.getElementById('leave-btn');
const muteBtn     = document.getElementById('mute-btn');
const micIcon     = document.getElementById('mic-icon');
const micOffIcon  = document.getElementById('mic-off-icon');
const peersEl     = document.getElementById('peers');
const emptyHint   = document.getElementById('empty-hint');
const statusEl    = document.getElementById('status');
const latencyEl   = document.getElementById('latency');
const roomNameEl  = document.getElementById('room-name');

// ── Helpers ────────────────────────────────────────────────────────────────
function setStatus(msg, connected = false) {
  statusEl.textContent = msg;
  statusEl.className = connected ? 'connected' : '';
}

function updateEmptyHint() {
  emptyHint.classList.toggle('hidden', peers.size > 0);
}

function initSocket() {
  socket = io({ transports: ['websocket'] });

  socket.on('connect', () => setStatus('Connected', true));
  socket.on('disconnect', () => setStatus('Disconnected'));

  // Server sends existing peers when we join
  socket.on('peers', async (peerIds) => {
    for (const id of peerIds) {
      await createOffer(id);
    }
  });

  // A new peer joined — they'll send us an offer
  socket.on('peer-joined', (id) => {
    // Nothing to do; initiator sends the offer
  });

  socket.on('offer', async ({ from, offer }) => {
    const pc = getOrCreatePC(from);
    await pc.setRemoteDescription(offer);
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    socket.emit('answer', { to: from, answer });
  });

  socket.on('answer', async ({ from, answer }) => {
    const entry = peers.get(from);
    if (entry) await entry.pc.setRemoteDescription(answer);
  });

  socket.on('ice-candidate', async ({ from, candidate }) => {
    const entry = peers.get(from);
    if (entry && candidate) {
      try { await entry.pc.addIceCandidate(candidate); } catch (_) {}
    }
  });

  socket.on('peer-left', (id) => removePeer(id));

  // Simple round-trip latency probe
  setInterval(() => {
    const t0 = Date.now();
    socket.volatile.emit('ping-probe', t0, () => {
      latencyEl.textContent = `~${Date.now() - t0}ms`;
    });
  }, 4000);
}

function getOrCreatePC(peerId) {
  if (peers.has(peerId)) return peers.get(peerId).pc;

  const pc = new RTCPeerConnection(ICE_CONFIG);

  // Add local tracks
  if (localStream) {
    localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));
  }

  // Trickle ICE — send candidates as they arrive
  pc.onicecandidate = ({ candidate }) => {
    if (candidate) socket.emit('ice-candidate', { to: peerId, candidate });
  };

  // Render remote audio
  pc.ontrack = ({ streams }) => {
    const audio = document.createElement('audio');
    audio.srcObject = streams[0];
    audio.autoplay = true;
    audio.dataset.peerId = peerId;
    document.body.appendChild(audio);

    // Speaking indicator via Web Audio
    attachVolumeIndicator(streams[0], peerId);
  };

  pc.onconnectionstatechange = () => {
    if (['failed', 'closed', 'disconnected'].includes(pc.connectionState)) {
      removePeer(peerId);
    }
  };

  const card = addPeerCard(peerId);
  peers.set(peerId, { pc, card });
  updateEmptyHint();
  return pc;
}

async function createOffer(peerId) {
  const pc = getOrCreatePC(peerId);

  // Prefer low-latency codec settings
  const offer = await pc.createOffer({ offerToReceiveAudio: true });

  // Tweak SDP: prefer Opus, set max bitrate low for voice (24 kbps)
  offer.sdp = preferOpus(offer.sdp);
  await pc.setLocalDescription(offer);
  socket.emit('offer', { to: peerId, offer });
}

function removePeer(peerId) {
  const entry = peers.get(peerId);
  if (!entry) return;
  entry.pc.close();
  entry.card.remove();
  peers.delete(peerId);
  // Remove audio element
  const audio = document.querySelector(`audio[data-peer-id="${peerId}"]`);
  if (audio) audio.remove();
  updateEmptyHint();
}

function addPeerCard(peerId) {
  const initials = peerId.slice(0, 2).toUpperCase();
  const card = document.createElement('div');
  card.className = 'peer-card';
  card.id = `peer-${peerId}`;
  card.innerHTML = `
    <div class="avatar">${initials}</div>
    <div class="peer-label">${peerId.slice(0, 8)}</div>
  `;
  peersEl.appendChild(card);
  return card;
}

// ── Volume / speaking indicator ────────────────────────────────────────────
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function attachVolumeIndicator(stream, peerId) {
  const source = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser);

  const data = new Uint8Array(analyser.frequencyBinCount);
  function tick() {
    analyser.getByteFrequencyData(data);
    const vol = data.reduce((a, b) => a + b, 0) / data.length;
    const card = document.getElementById(`peer-${peerId}`);
    if (card) card.classList.toggle('speaking', vol > 8);
    if (peers.has(peerId)) requestAnimationFrame(tick);
  }
  tick();
}

function attachSelfVolumeIndicator(stream) {
  const source = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser);

  const data = new Uint8Array(analyser.frequencyBinCount);
  const selfCard = document.querySelector('.self-peer');
  function tick() {
    analyser.getByteFrequencyData(data);
    const vol = data.reduce((a, b) => a + b, 0) / data.length;
    if (selfCard) selfCard.classList.toggle('speaking', vol > 8 && !muted);
    requestAnimationFrame(tick);
  }
  tick();
}

// ── SDP helpers (reduce Opus bitrate for lower latency) ───────────────────
function preferOpus(sdp) {
  // Set Opus max bitrate to 24 kbps — plenty for voice, cuts jitter
  return sdp.replace(
    /a=fmtp:(\d+) (.*useinbandfec=1.*)/g,
    'a=fmtp:$1 $2;maxaveragebitrate=24000;cbr=1'
  );
}

// ── UI events ──────────────────────────────────────────────────────────────
joinBtn.addEventListener('click', async () => {
  const room = roomInput.value.trim();
  if (!room) return;

  try {
    localStream = await navigator.mediaDevices.getUserMedia(AUDIO_CONSTRAINTS);
    // Resume AudioContext on first user gesture
    if (audioCtx.state === 'suspended') audioCtx.resume();
    attachSelfVolumeIndicator(localStream);
  } catch (err) {
    alert('Microphone access denied. Please allow mic access and try again.');
    return;
  }

  initSocket();
  socket.emit('join', room);
  currentRoom = room;

  roomNameEl.textContent = room;
  joinPanel.classList.add('hidden');
  roomPanel.classList.remove('hidden');
  updateEmptyHint();
});

leaveBtn.addEventListener('click', () => {
  peers.forEach((_, id) => removePeer(id));
  if (localStream) localStream.getTracks().forEach((t) => t.stop());
  if (socket) socket.disconnect();
  socket = null;
  localStream = null;
  currentRoom = null;
  roomPanel.classList.add('hidden');
  joinPanel.classList.remove('hidden');
  setStatus('Disconnected');
  latencyEl.textContent = '';
});

muteBtn.addEventListener('click', () => {
  muted = !muted;
  if (localStream) {
    localStream.getAudioTracks().forEach((t) => { t.enabled = !muted; });
  }
  muteBtn.classList.toggle('muted', muted);
  micIcon.classList.toggle('hidden', muted);
  micOffIcon.classList.toggle('hidden', !muted);
});

roomInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') joinBtn.click();
});
