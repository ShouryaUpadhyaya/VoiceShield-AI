const { io } = require("socket.io-client");
const socket = io("http://localhost:8010/dashboard", { transports: ['websocket'] });
socket.on("connect", () => console.log("Connected to dashboard"));
socket.on("stats", (msg) => console.log("Stats:", msg.session_id));
socket.on("chunk_created", (msg) => console.log("Chunk:", msg.session_id));
