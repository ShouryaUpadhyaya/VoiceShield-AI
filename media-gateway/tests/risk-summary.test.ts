import { describe, it, expect } from 'vitest';
import { summarizeRisk } from '../src/risk-summary.js';

describe('call risk summary', () => {
  it('does not count unknown or invalid scores as genuine', () => {
    const results = [null, undefined, NaN, Infinity, -1, 2, '0.5', .8, 0]
      .map(value => ({ signals: { deepfake_probability: value } }));
    expect(summarizeRisk(results)).toEqual({ meanPct: 40, peakPct: 80, scoredWindows: 2, unscoredWindows: 7, calibrated: false });
  });
  it('abstains when no windows were scored', () => {
    expect(summarizeRisk([{ signals: { deepfake_probability: null } }]).meanPct).toBeNull();
  });
  it('includes chunks for which no result has arrived', () => {
    expect(summarizeRisk([], 4).unscoredWindows).toBe(4);
  });
});
