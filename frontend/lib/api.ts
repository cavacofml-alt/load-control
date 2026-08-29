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

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
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

  return (await response.json()) as T;
}

export async function calculateLoad(payload: CalculateRequest): Promise<CalculateResponse> {
  return apiRequest<CalculateResponse>("/api/v1/load-control/calculate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface AircraftEnvelope {
  registration: string;
  type_designator: string;
  mzfw: number;
  mtow: number;
  mlaw: number;
  dow: number;
  doi: number;
  lemac: number;
  mac_length: number;
  k_constant: number;
  c_constant: number;
  reference_station: number;
}

export async function getAircraftEnvelope(registration: string): Promise<AircraftEnvelope> {
  return apiRequest<AircraftEnvelope>(`/api/v1/aircraft/${registration}`);
}

export interface Flight {
  id: string;
  flight_number: string;
  origin: string;
  destination: string;
  std: string;
  status: "SCHEDULED" | "CLOSED" | "DEPARTED" | "CANCELLED";
  aircraft_registration: string | null;
}

export interface Loadsheet {
  id: string;
  flight_id: string;
  version: number;
  supersedes_id: string | null;
  document_type: "FINAL" | "LMC";
  zfw: number;
  tow: number;
  law: number;
  zfw_cg: number;
  zfw_mac: number;
  // NULL até o motor de cálculo suportar o índice de combustível (Secção C
  // do AHM565) — uma loadsheet com estes campos a null não está certificada.
  tow_cg: number | null;
  tow_mac: number | null;
  total_index: number;
  signed_by: string;
  signed_at: string;
}

export interface SignLoadsheetRequest {
  flight_id: string;
  take_off_fuel: number;
  trip_fuel: number;
  pax_loads?: Record<string, Record<string, number> | number>;
  hold_loads?: Record<string, HoldLoadItem>;
}

export async function listFlights(): Promise<Flight[]> {
  return apiRequest<Flight[]>("/api/v1/flights");
}

export async function getFlight(flightId: string): Promise<Flight> {
  return apiRequest<Flight>(`/api/v1/flights/${flightId}`);
}

export async function getLoadsheetHistory(flightId: string): Promise<Loadsheet[]> {
  return apiRequest<Loadsheet[]>(`/api/v1/loadsheets/${flightId}`);
}

export async function signLoadsheet(payload: SignLoadsheetRequest): Promise<Loadsheet> {
  return apiRequest<Loadsheet>("/api/v1/loadsheets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
