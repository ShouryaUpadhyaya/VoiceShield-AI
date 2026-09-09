import { describe, expect, it } from 'vitest';
import { rankChunksByAiScore } from '../lib/chunk-ranking';

describe('rankChunksByAiScore', () => {
  it('orders highest AI score first and resolves equal scores by earlier chunk', () => {
    const ranked = rankChunksByAiScore([
      { sequence: 8, deepfakeScore: 0.82 },
      { sequence: 2, deepfakeScore: 0.91 },
      { sequence: 4, deepfakeScore: 0.91 },
      { sequence: 1, deepfakeScore: null },
    ]);

    expect(ranked.map(chunk => chunk.sequence)).toEqual([2, 4, 8, 1]);
  });

  it('keeps chunks without an ML score below scored chunks in chronological order', () => {
    const ranked = rankChunksByAiScore([
      { sequence: 9, deepfakeScore: undefined },
      { sequence: 3, deepfakeScore: null },
      { sequence: 5, deepfakeScore: 0.1 },
    ]);

    expect(ranked.map(chunk => chunk.sequence)).toEqual([5, 3, 9]);
  });
});
