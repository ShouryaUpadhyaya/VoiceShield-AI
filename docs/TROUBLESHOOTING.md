# Troubleshooting

**Problem**: CallVault WebSocket audio was not reaching the Media Gateway dashboard.

**Root Cause**: The initial WebSocket implementation was placed in `HandoffReceiver.kt`, which only runs when CallVault's Handoff architecture (`startHandoff`) succeeds. On the test device (OnePlus, ColorOS), the native `libaudiohandoff.so` fails to resolve, causing `startHandoff` to crash. CallVault correctly falls back to `DirectAudioRecorderSession` (daemon direct capture), which records locally. But since `HandoffReceiver` never ran, the WebSocket never connected.

**Fix**: Moved WebSocket streaming into `DirectAudioRecorderSession.kt` (the daemon's fallback capture path). The gateway URL and session ID are now passed through the AIDL interface.

**Network Configuration**:
- Media Gateway binds to `0.0.0.0:8010` (all interfaces)
- CallVault connects to `ws://<laptop-LAN-IP>:8010`
- The laptop LAN IP changes when switching WiFi networks
- The phone must be on the SAME WiFi network as the laptop
- `android:usesCleartextTraffic="true"` is required in AndroidManifest.xml for `ws://` (not `wss://`)

**Verifying the Gateway is Listening**:
```bash
curl http://localhost:8010/health
```

**Verifying the Phone Can Reach the Gateway**:
```bash
adb shell "curl -s http://<laptop-IP>:8010/health"
```

**Finding the Laptop LAN IP**:
```bash
ip route get 1.1.1.1 | head -1
# or
hostname -I
```

**ADB Wireless Debugging Commands**:
```bash
adb pair <ip:port> <pairing_code>
adb connect <ip:port>
adb devices
```

**Logcat Filtering**:
```bash
adb logcat | grep 'CV:WsSink'        # WebSocket connection logs
adb logcat | grep 'DirectAudioRec'   # Daemon capture logs
adb logcat | grep 'RecorderServer'   # Daemon server logs
```

**Common Failures**:
- "Connection refused" → Gateway not running, or wrong IP
- No logs at all from CV:WsSink → Media Gateway not enabled in CallVault settings, or gateway URL not configured
- Phone can't reach gateway → Different WiFi networks, or firewall blocking port 8010
- Dashboard shows "No active sessions" but gateway health shows a session → Dashboard WebSocket to `/dashboard` not connected (check browser console)

## Development Infrastructure

### Docker unavailable

```bash
docker info
```
If Docker daemon is not running, start Docker before: `docker compose up -d postgres`

### Port 5432 occupied

```bash
ss -ltnp | grep 5432
```
Do not kill unrelated PostgreSQL processes automatically. Use the configured `15432` port for the Compose setup.

### Port 8010 occupied

```bash
lsof -i :8010
```
If the existing Media Gateway is running, do not start another copy.

### Database authentication error

Verify:
```
DATABASE_URL
```
matches:
```
postgresql://postgres:voiceshield@localhost:15432/voiceshield
```
for the Docker configuration.

### Frontend cannot connect

Verify:
- Media Gateway: `http://localhost:8010`
- Frontend: `http://localhost:3000`
- `NEXT_PUBLIC_GATEWAY_URL` is set to `http://localhost:8010` in `frontend/.env.local`
