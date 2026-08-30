import os from 'node:os';

export interface NetworkInterfaceInfo {
  name: string;
  ip: string;
  type: 'wifi' | 'ethernet' | 'docker' | 'unknown';
}

export function getLocalIpAddresses(): NetworkInterfaceInfo[] {
  const interfaces = os.networkInterfaces();
  const results: NetworkInterfaceInfo[] = [];

  for (const [name, nets] of Object.entries(interfaces)) {
    if (!nets) continue;

    for (const net of nets) {
      // Skip internal and non-IPv4 addresses
      if (net.family === 'IPv4' && !net.internal) {
        let type: NetworkInterfaceInfo['type'] = 'unknown';
        const lowerName = name.toLowerCase();

        if (lowerName.includes('wl') || lowerName.includes('wi-fi') || lowerName.includes('airport')) {
          type = 'wifi';
        } else if (lowerName.includes('eth') || lowerName.includes('en') || lowerName.includes('lan')) {
          type = 'ethernet';
        } else if (lowerName.includes('docker') || lowerName.includes('br-') || lowerName.includes('veth')) {
          type = 'docker';
        }

        results.push({ name, ip: net.address, type });
      }
    }
  }

  // Sort: wifi first, then ethernet, then unknown, docker last
  results.sort((a, b) => {
    const rank = { wifi: 1, ethernet: 2, unknown: 3, docker: 4 };
    return rank[a.type] - rank[b.type];
  });

  return results;
}

export function getRecommendedLanIp(): string {
  const ips = getLocalIpAddresses();
  // Filter out docker if possible, prefer wifi or ethernet
  const validIps = ips.filter(i => i.type !== 'docker');
  if (validIps.length > 0) {
    return validIps[0].ip;
  }
  if (ips.length > 0) {
    return ips[0].ip;
  }
  return '127.0.0.1';
}
