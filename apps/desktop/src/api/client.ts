// The only place the UI talks to the inference backend. Nothing outside
// this file should know the API shape or base URL.
const BASE_URL = "http://127.0.0.1:8000";

export interface GenerateImageRequest {
  prompt: string;
  negativePrompt?: string;
  width?: number;
  height?: number;
  steps?: number;
  seed?: number;
}

export interface GenerateImageResponse {
  file_path: string;
  prompt: string;
  seed: number;
  device: string;
  model_id: string;
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}): ${body}`);
  }
  return response.json() as Promise<T>;
}

export async function generateImage(
  request: GenerateImageRequest,
): Promise<GenerateImageResponse> {
  const response = await fetch(`${BASE_URL}/generate/image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: request.prompt,
      negative_prompt: request.negativePrompt,
      width: request.width,
      height: request.height,
      steps: request.steps,
      seed: request.seed,
    }),
  });

  return parseOrThrow<GenerateImageResponse>(response);
}

export interface HealthResponse {
  status: string;
  selected_device: {
    name: string;
    backend: string;
    total_vram_mb: number | null;
    free_vram_mb: number | null;
  };
  model_id: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BASE_URL}/health`);
  return parseOrThrow<HealthResponse>(response);
}
