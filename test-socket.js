const { io } = require("socket.io-client");
const socket = io("http://localhost:8010/dashboard", { transports: ['websocket'] });
socket.on("connect", () => console.log("Connected to dashboard"));
socket.on("gateway_state", (msg) => { console.log("Got state:", msg); socket.disconnect(); process.exit(0); });
socket.on("connect_error", (err) => { console.error("Error:", err.message); process.exit(1); });
setTimeout(() => { console.log("Timeout"); process.exit(1); }, 5000);
