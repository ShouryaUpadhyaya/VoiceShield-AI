# CallVault Android Application

CallVault is the Android component of VoiceShield-AI. It is responsible for capturing audio during active phone calls.

## Features
- Background service for seamless recording.
- Captures system microphone and uplink/downlink call audio.
- Connects directly to the Media Gateway via WebSocket.
- Streams audio in near real-time (raw PCM format).

## Configuration
When starting CallVault, you enter the IP address of the Media Gateway (e.g., `192.168.1.5`). Ensure both the laptop and the phone are on the same Wi-Fi network.

The Media Gateway dashboard will automatically recommend the correct IP address to use on your LAN.
