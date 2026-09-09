/** Descriptive call score: unknown windows are never counted as genuine. */
export function summarizeRisk(results: any[], totalWindows = results.length) {
  const scores = results.map(r => r?.signals?.deepfake_probability)
    .filter((v): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1);
  return {
    meanPct: scores.length ? 100 * scores.reduce((a, b) => a + b, 0) / scores.length : null,
    peakPct: scores.length ? 100 * Math.max(...scores) : null,
    scoredWindows: scores.length,
    unscoredWindows: Math.max(totalWindows, results.length) - scores.length,
    calibrated: false,
  };
}
