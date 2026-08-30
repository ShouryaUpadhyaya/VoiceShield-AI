import { FusionWeights } from '../stores/ml-lab-store';

const ML_SERVER_URL = process.env.NEXT_PUBLIC_ML_URL || (typeof window !== 'undefined' ? `http://${window.location.hostname}:8011` : 'http://localhost:8011');
const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || (typeof window !== 'undefined' ? `http://${window.location.hostname}:8010` : 'http://localhost:8010');

export class MlApi {
  static async getModels() {
    const res = await fetch(`${ML_SERVER_URL}/api/models`);
    if (!res.ok) throw new Error('Failed to fetch models');
    return res.json();
  }

  static async getFusionConfig() {
    const res = await fetch(`${ML_SERVER_URL}/api/config/fusion`);
    if (!res.ok) throw new Error('Failed to fetch fusion config');
    return res.json();
  }

  static async updateFusionConfig(weights: FusionWeights) {
    const res = await fetch(`${ML_SERVER_URL}/api/config/fusion`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ weights })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update fusion config');
    }
    return res.json();
  }

  static async runModel(modelName: string, file: File) {
    const formData = new FormData();
    formData.append('audio', file);
    const res = await fetch(`${ML_SERVER_URL}/api/inference/${modelName}`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to run ${modelName}`);
    }
    const data = await res.json();
    
    // Save to gateway DB in background
    this.saveTestRun(file.name, data, false, modelName);
    
    return data;
  }

  static async runPipeline(file: File) {
    const formData = new FormData();
    formData.append('audio', file);
    const res = await fetch(`${ML_SERVER_URL}/api/inference/pipeline`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to run pipeline');
    }
    const data = await res.json();
    
    // Save to gateway DB in background
    this.saveTestRun(file.name, data, true);
    
    return data;
  }
  
  static async getTestHistory() {
    const res = await fetch(`${GATEWAY_URL}/api/tests`);
    if (!res.ok) throw new Error('Failed to fetch test history');
    return res.json();
  }

  private static async saveTestRun(filename: string, resultData: any, isPipeline: boolean, modelName?: string) {
    try {
      await fetch(`${GATEWAY_URL}/api/tests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename,
          duration: resultData.input?.durationSec,
          model: modelName,
          model_version: resultData.modelVersion,
          status: resultData.status,
          latency_ms: resultData.latencyMs,
          result_json: resultData.result,
          fusion_config_json: resultData.result?.fusion,
          final_score: resultData.result?.fusion?.aiGeneratedScore,
          is_pipeline: isPipeline
        })
      });
    } catch (e) {
      console.error('Failed to save test history to DB', e);
    }
  }
}
