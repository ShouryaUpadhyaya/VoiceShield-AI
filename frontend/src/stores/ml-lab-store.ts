import { create } from 'zustand';

export interface ModelStatus {
  status: 'ready' | 'loading' | 'error' | 'unavailable';
  version?: string;
  reason?: string;
  device?: string;
}

export interface FusionWeights {
  indic: number;
  dhwani: number;
  customDeepfake: number;
  prosody: number;
}

export interface MlLabState {
  modelsStatus: Record<string, ModelStatus>;
  fusionWeights: FusionWeights;
  previewWeights: FusionWeights;
  currentFile: File | null;
  
  setModelsStatus: (statuses: Record<string, ModelStatus>) => void;
  setFusionWeights: (weights: FusionWeights) => void;
  setPreviewWeights: (weights: FusionWeights) => void;
  setCurrentFile: (file: File | null) => void;
  resetPreviewWeights: () => void;
  normalizePreviewWeights: () => void;
}

export const useMlLabStore = create<MlLabState>((set, get) => ({
  modelsStatus: {},
  fusionWeights: {
    indic: 0.45,
    dhwani: 0.20,
    customDeepfake: 0.20,
    prosody: 0.15,
  },
  previewWeights: {
    indic: 0.45,
    dhwani: 0.20,
    customDeepfake: 0.20,
    prosody: 0.15,
  },
  currentFile: null,

  setModelsStatus: (statuses) => set({ modelsStatus: statuses }),
  setFusionWeights: (weights) => set({ fusionWeights: weights, previewWeights: weights }),
  setPreviewWeights: (weights) => set({ previewWeights: weights }),
  setCurrentFile: (file) => set({ currentFile: file }),
  
  resetPreviewWeights: () => set((state) => ({ previewWeights: state.fusionWeights })),
  normalizePreviewWeights: () => set((state) => {
    const total = Object.values(state.previewWeights).reduce((sum, val) => sum + val, 0);
    if (total === 0) return state; // Avoid division by zero
    
    return {
      previewWeights: {
        indic: Number((state.previewWeights.indic / total).toFixed(4)),
        dhwani: Number((state.previewWeights.dhwani / total).toFixed(4)),
        customDeepfake: Number((state.previewWeights.customDeepfake / total).toFixed(4)),
        prosody: Number((state.previewWeights.prosody / total).toFixed(4)),
      }
    };
  })
}));
