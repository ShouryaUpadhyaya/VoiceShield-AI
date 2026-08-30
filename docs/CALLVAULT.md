# CallVault

- CallVault is a separate git repository at `CallVault/` in the project root
- It is a forked FOSS Android call recording app
- Original project: CallVault by kitsumed
- Requires Android 11+ (API 30)
- Uses embedded ADB + Wireless Debugging for privileged audio capture

**Wireless Debugging Setup**:
1. Enable Developer Options on the Android phone
2. Enable Wireless Debugging
3. Note the pairing code and IP:port
4. Run: `adb pair <ip:port> <pairing_code>`
5. Run: `adb connect <ip:port>`
6. Verify: `adb devices`

**Building the APK**:
```bash
cd CallVault
./gradlew assembleDebug
```
Output: `app/build/outputs/apk/debug/app-debug.apk`

**Installing**:
```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

**Configuring the Gateway URL**:
1. Open CallVault on the phone
2. Go to Settings
3. Enable "Media Gateway"
4. Set the WebSocket URL to `ws://<laptop-LAN-IP>:8010`
5. The laptop LAN IP can be found with `ip route` or `hostname -I`

**Expected Audio Format**: 48 kHz, mono, PCM 16-bit signed little-endian

**WebSocket Behavior**: On each phone call, CallVault's daemon:
1. Opens a WebSocket to the configured gateway URL
2. Sends `session.start` JSON with session_id, source="CallVault", sample_rate=48000, channels=1, encoding="pcm_s16le"
3. Streams raw PCM binary frames in real-time from the `captureLoop`
4. Sends `session.stop` JSON when the call ends
5. Closes the WebSocket

**Troubleshooting**:
- If the gateway URL is wrong or the laptop is unreachable, the WebSocket fails silently — local recording continues normally
- Use `adb logcat | grep 'CV:WsSink'` to see WebSocket connection/error logs from the daemon
- Verify the phone can reach the gateway: `adb shell curl -s http://<laptop-IP>:8010/health`
