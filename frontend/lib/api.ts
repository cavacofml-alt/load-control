export interface HoldLoadItem {
  uld_type: string;
  weight: number;
}

export interface CalculateRequest {
  registration: string;
  take_off_fuel: number;
  trip_fuel: number;
  pax_loads?: Record<string, Record<string, number> | number>;
  hold_loads?: Record<string, HoldLoadItem>;
}

export interface CalculateResponse {
  zfw: number;
  tow: number;
  ldw: number;
  lizfw: number;
  mac_zfw: number;
  zfw_within_limits: boolean;
  tow_within_limits: boolean;
  ldw_within_limits: boolean;
  within_limits: boolean;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function apiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new Error(
      "NEXT_PUBLIC_API_URL não está definida — configura-a no .env.local (dev) ou nas env vars da Vercel (produção)."
    );
  }
  return url;
}

export async function calculateLoad(payload: CalculateRequest): Promise<CalculateResponse> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/load-control/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body?.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // resposta sem corpo JSON válido — mantém o statusText
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as CalculateResponse;
}
