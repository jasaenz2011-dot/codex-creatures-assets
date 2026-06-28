const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  transports: ['websocket'],   // skip long-polling to cut one RTT
  pingInterval: 5000,
  pingTimeout: 3000,
});

app.use(express.static(path.join(__dirname, 'public')));

// rooms[roomId] = Set of socket ids
const rooms = {};

io.on('connection', (socket) => {
  let currentRoom = null;

  socket.on('join', (roomId) => {
    currentRoom = roomId;
    if (!rooms[roomId]) rooms[roomId] = new Set();

    // Send existing peers to the new joiner
    const peers = [...rooms[roomId]];
    socket.emit('peers', peers);

    // Tell existing peers about the new joiner
    peers.forEach((peerId) => {
      io.to(peerId).emit('peer-joined', socket.id);
    });

    rooms[roomId].add(socket.id);
    socket.join(roomId);
  });

  // Relay WebRTC signaling messages directly between peers
  socket.on('offer', ({ to, offer }) => {
    io.to(to).emit('offer', { from: socket.id, offer });
  });

  socket.on('answer', ({ to, answer }) => {
    io.to(to).emit('answer', { from: socket.id, answer });
  });

  socket.on('ice-candidate', ({ to, candidate }) => {
    io.to(to).emit('ice-candidate', { from: socket.id, candidate });
  });

  socket.on('disconnect', () => {
    if (currentRoom && rooms[currentRoom]) {
      rooms[currentRoom].delete(socket.id);
      if (rooms[currentRoom].size === 0) delete rooms[currentRoom];
      socket.to(currentRoom).emit('peer-left', socket.id);
    }
  });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Voice chat server running at http://localhost:${PORT}`);
});
