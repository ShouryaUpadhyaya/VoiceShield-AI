# ML Fusion System

VoiceShield-AI determines the likelihood that an audio chunk is AI-generated (spoofed/deepfake) by aggregating the predictions from multiple distinct ML models into a single, unified "AI Likelihood Score".

## Weighted Mean Strategy

To combine the outputs, we use a **Weighted Mean** strategy. Each model outputs a synthetic probability score `[0, 1]`, which is multiplied by a predefined weight. The sum of these products yields the final fusion score.

The default weights are configured to prioritize detection in Indic-language scenarios, while still falling back on general-purpose models for robustness:

| Detector | Default Weight | Environment Variable | Rationale |
|----------|----------------|----------------------|-----------|
| **Indic** | 0.45 (45%) | `FUSION_INDIC_WEIGHT` | Highest priority. Specifically tuned for Indian accents, regional languages, and local scam tactics. |
| **Dhwani** | 0.20 (20%) | `FUSION_DHWANI_WEIGHT` | General-purpose anti-spoofing based on well-established open-source architectures. |
| **Custom** | 0.20 (20%) | `FUSION_CUSTOM_WEIGHT` | A secondary deepfake classifier that acts as a strong generalized fallback. |
| **Prosody** | 0.15 (15%) | `FUSION_PROSODY_WEIGHT` | Analyzes acoustic anomalies (pitch, jitter, shimmer). Since it is not purely spectral, it provides a complementary signal but gets lower weight. |

## Handling Missing or Failed Models

In a microservice architecture, it is common for a specific model to fail—whether due to missing weights at startup, an out-of-memory error during inference, or simply because it was disabled by the operator.

The fusion layer employs a **dynamic weight re-normalization** policy:
1. It identifies which models successfully returned a score for the current chunk.
2. It gathers the raw weights of only the available models.
3. It divides each available model's weight by the sum of the available weights, yielding a new set of normalized weights that perfectly sum to 1.0 (100%).
4. It calculates the final score using these normalized weights.

This prevents the overall score from artificially deflating (e.g., scoring a 0.0 just because a model crashed). If *no* models are available, the fusion system returns `None` (null) for the deepfake probability.

## Call-Level Pooling

The fusion score is calculated **per 3-second chunk** within the Python ML service. 
The Node.js Media Gateway consumes these chunk-level fusion scores and aggregates them across the entire duration of the call (currently using a simple mean) to assign the final `ai_likelihood_pct` stored in the database.
