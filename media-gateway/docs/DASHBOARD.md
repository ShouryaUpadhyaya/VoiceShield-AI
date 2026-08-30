# Observability Dashboard

The Media Gateway includes an engineering dashboard located at `http://localhost:8010/`.

## Features
- **LAN Discovery**: Automatically displays the recommended WebSocket URL (e.g., `ws://192.168.x.x:8010`) to enter into CallVault.
- **Global Overview**: Real-time cards displaying Total Calls, Total Audio, and Database Connection Status.
- **Session Tracking**: Displays active calls, tracking real-time RMS (volume), received bytes, and a 3-second buffer progress bar.
- **Chunk Timeline**: Visualizes exactly when 3-second chunks are completed and dispatched to the ML Service.
- **Historical Data**: A table listing previous calls along with an option to download their full `.wav` recordings.
