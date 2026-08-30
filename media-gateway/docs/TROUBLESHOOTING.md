# Troubleshooting

### CallVault Cannot Connect
- Ensure the Android device and laptop are on the exact same Wi-Fi network.
- Check the Media Gateway dashboard (`http://localhost:8010/`) and use the IP displayed under "Android Connection".
- Ensure any VPNs or Firewalls on the laptop are disabled.

### No Chunks Emitted
- If you see "STREAMING" but no chunks appear, the buffer has not reached 3.0 seconds. 
- Ensure you are sending the correct sample rate (e.g., if you specify 48kHz, the Gateway expects 288,000 bytes per chunk). If you send data too slowly, the 3-second limit is never reached.

### Database Connection Fails
- Ensure PostgreSQL is running (`docker compose up -d postgres`).
- Check your `.env` `DATABASE_URL` matches the credentials used in your docker-compose file.

### Tests Fail
- Ensure you are using a modern version of Node (18+). Run `npm install` to ensure Vitest is correctly installed.
