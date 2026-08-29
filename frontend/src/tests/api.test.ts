import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getWebsocketUrl, fetchStats, getRecordingUrl } from '../lib/api';

describe('API Utils', () => {
  const originalEnv = process.env;
  const originalWindow = global.window;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
    global.window = originalWindow;
    vi.unstubAllGlobals();
  });

  it('should use window.location.hostname for getWebsocketUrl when window is defined', () => {
    vi.stubGlobal('window', { location: { hostname: '10.59.60.11' } });
    
    // We have to reset the API module to re-evaluate the GATEWAY_URL constant
    vi.resetModules();
    
    // In Vitest, resetting modules and dynamically importing is the easiest way to test module-level constants
    return import('../lib/api').then((api) => {
      expect(api.getWebsocketUrl()).toBe('ws://10.59.60.11:8010/dashboard');
    });
  });

  it('should fallback to localhost if window is undefined and no env var', () => {
    delete process.env.NEXT_PUBLIC_GATEWAY_URL;
    vi.stubGlobal('window', undefined);
    
    vi.resetModules();
    
    return import('../lib/api').then((api) => {
      expect(api.getWebsocketUrl()).toBe('ws://localhost:8010/dashboard');
    });
  });

  it('should prioritize NEXT_PUBLIC_GATEWAY_URL if provided', () => {
    process.env.NEXT_PUBLIC_GATEWAY_URL = 'http://custom-host:8010';
    vi.stubGlobal('window', { location: { hostname: '10.59.60.11' } });
    
    vi.resetModules();
    
    return import('../lib/api').then((api) => {
      expect(api.getWebsocketUrl()).toBe('ws://custom-host:8010/dashboard');
    });
  });
});
