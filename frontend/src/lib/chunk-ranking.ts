export interface RankableChunk {
  sequence: number;
  deepfakeScore?: number | null;
}

/** Highest AI-evidence first; equal or unknown values remain chronological. */
export function rankChunksByAiScore<T extends RankableChunk>(chunks: T[]): T[] {
  return [...chunks].sort((left, right) => {
    const leftScore = left.deepfakeScore;
    const rightScore = right.deepfakeScore;
    const leftIsScored = typeof leftScore === 'number' && Number.isFinite(leftScore);
    const rightIsScored = typeof rightScore === 'number' && Number.isFinite(rightScore);

    if (leftIsScored && rightIsScored && leftScore !== rightScore) return rightScore - leftScore;
    if (leftIsScored !== rightIsScored) return leftIsScored ? -1 : 1;
    return left.sequence - right.sequence;
  });
}
