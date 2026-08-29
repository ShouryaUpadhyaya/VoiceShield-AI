const { io } = require("socket.io-client");
const ioSocket = io('http://localhost:8010/dashboard', { transports: ['websocket'] });
ioSocket.on('connect', () => console.log('ONLINE'));
ioSocket.on('gateway_state', (msg) => console.log('GATEWAY STATE', msg));
ioSocket.on('stats', (msg) => console.log('STATS', msg.session_id));
