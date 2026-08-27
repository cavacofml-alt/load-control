"use client";

import { useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiError, calculateLoad, type CalculateResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Dados estáticos da aeronave (limites estruturais reais do TC-JNH) e valores
// mock para o que a API ainda não calcula (TOW/LDW — não há conceito de
// combustível no sistema hoje, só ZFW). Passageiros e carga vêm do estado,
// ligados ao POST /calculate real via lib/api.ts.
// ---------------------------------------------------------------------------

const FLIGHT = {
  route: "FRA-FAO",
  registration: "TC-JNH",
  std: "14:35Z",
  etd: "14:50Z",
};

const AIRCRAFT = {
  dow: 125187,
  doi: 89.2,
  mzfw: 175000,
  mtow: 233000,
  mlaw: 187000,
};

// Combustível por defeito (kg) — só valores iniciais para os inputs.
const DEFAULT_TAKE_OFF_FUEL = 60000;
const DEFAULT_TRIP_FUEL = 32000;

// O backend não calcula o efeito do combustível no índice/CG (precisaria da
// tabela de índice por tanque da Secção C do AHM565) — por isso a posição
// horizontal (%MAC) do TOW/LDW no envelope continua estimada, mesmo que o
// peso (vertical) já seja real.
const MAC_ESTIMATE = { tow: 27.4, ldw: 25.8 };

const INITIAL_CABIN_ZONES = [
  { code: "0A", label: "Zona 0A · FWD", capacity: 28, pax: 24 },
  { code: "0B", label: "Zona 0B · MID", capacity: 138, pax: 120 },
  { code: "0C", label: "Zona 0C · AFT", capacity: 123, pax: 98 },
];

const INITIAL_CARGO_ROWS = [
  { position: "11P", uldType: "PMC", weight: 3200 },
  { position: "21", uldType: "PLA", weight: 2100 },
  { position: "32L", uldType: "AKE", weight: 980 },
  { position: "CPT51", uldType: "BULK", weight: 220 },
];

const ULD_TYPES = ["AKE", "PKC", "PLA", "PAG", "PMC", "BULK"];

// Envelope de CG (polígono fechado) — forma ilustrativa, não os limites
// certificados reais do A330-300 (esses vivem na Secção C do AHM565).
const ENVELOPE_POLYGON = [
  { mac: 18, weight: 110000 },
  { mac: 15, weight: 175000 },
  { mac: 24, weight: 233000 },
  { mac: 38, weight: 233000 },
  { mac: 34, weight: 175000 },
  { mac: 28, weight: 110000 },
  { mac: 18, weight: 110000 },
];

const DEBOUNCE_MS = 500;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatKg(value: number) {
  return `${Math.round(value).toLocaleString("en-US")} kg`;
}

function gaugeColor(ratio: number) {
  if (ratio >= 1) return "bg-red-500";
  if (ratio >= 0.92) return "bg-amber-500";
  return "bg-emerald-500";
}

function WeightGauge({
  label,
  actual,
  limit,
}: {
  label: string;
  actual: number;
  limit: number;
}) {
  const ratio = actual / limit;
  const pct = Math.min(ratio, 1) * 100;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {label}
        </span>
        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
          {formatKg(actual)} <span className="text-slate-400 dark:text-slate-500">/ {formatKg(limit)}</span>
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div
          className={`h-full rounded-full transition-all ${gaugeColor(ratio)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="self-end text-[11px] text-slate-400 dark:text-slate-500">
        {(ratio * 100).toFixed(1)}% do limite
      </span>
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
        {title}
      </h2>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Home() {
  const [cabinZones, setCabinZones] = useState(INITIAL_CABIN_ZONES);
  const [cargoRows, setCargoRows] = useState(INITIAL_CARGO_ROWS);
  const [takeOffFuel, setTakeOffFuel] = useState(DEFAULT_TAKE_OFF_FUEL);
  const [tripFuel, setTripFuel] = useState(DEFAULT_TRIP_FUEL);

  const [result, setResult] = useState<CalculateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Evita que uma resposta antiga (pedido lento) sobreponha um cálculo mais
  // recente quando o utilizador edita rapidamente vários campos seguidos.
  const requestIdRef = useRef(0);

  function updatePax(code: string, pax: number) {
    setCabinZones((zones) => zones.map((z) => (z.code === code ? { ...z, pax } : z)));
  }

  function updateCargoRow(index: number, field: "position" | "uldType" | "weight", value: string | number) {
    setCargoRows((rows) => rows.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  }

  useEffect(() => {
    const currentRequestId = ++requestIdRef.current;

    const timer = setTimeout(async () => {
      setLoading(true);

      const pax_loads = Object.fromEntries(
        cabinZones.map((zone) => [zone.code, { ADULT: zone.pax }])
      );
      const hold_loads = Object.fromEntries(
        cargoRows
          .filter((row) => row.position.trim() !== "")
          .map((row) => [row.position, { uld_type: row.uldType, weight: row.weight }])
      );

      try {
        const response = await calculateLoad({
          registration: FLIGHT.registration,
          take_off_fuel: takeOffFuel,
          trip_fuel: tripFuel,
          pax_loads,
          hold_loads,
        });
        if (requestIdRef.current === currentRequestId) {
          setResult(response);
          setError(null);
        }
      } catch (err) {
        if (requestIdRef.current === currentRequestId) {
          setResult(null);
          setError(err instanceof ApiError ? `(${err.status}) ${err.message}` : "Falha ao contactar a API.");
        }
      } finally {
        if (requestIdRef.current === currentRequestId) {
          setLoading(false);
        }
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [cabinZones, cargoRows, takeOffFuel, tripFuel]);

  const isSecure = result !== null && result.within_limits && error === null;
  const badgeLabel = loading && result === null ? "A CALCULAR…" : isSecure ? "FLIGHT SECURE" : "OUT OF LIMITS";
  const badgeIsNeutral = loading && result === null;

  const zfwPoint = result
    ? { mac: result.mac_zfw, weight: result.zfw, label: "ZFW" }
    : null;

  // TOW/LDW: peso real quando há resultado, senão uma estimativa a partir do
  // DOW + combustível introduzido. O %MAC continua estimado em ambos os casos
  // (ver nota sobre MAC_ESTIMATE acima).
  const towWeight = result?.tow ?? AIRCRAFT.dow + takeOffFuel;
  const ldwWeight = result?.ldw ?? AIRCRAFT.dow + takeOffFuel - tripFuel;
  const towPoint = { mac: MAC_ESTIMATE.tow, weight: towWeight, label: "TOW" };
  const ldwPoint = { mac: MAC_ESTIMATE.ldw, weight: ldwWeight, label: "LDW" };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50 font-sans text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      {/* Top Bar */}
      <header className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-6">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              Voo
            </div>
            <div className="text-lg font-bold tracking-tight">{FLIGHT.route}</div>
          </div>
          <div className="h-8 w-px bg-slate-200 dark:bg-slate-800" />
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              Matrícula
            </div>
            <div className="text-lg font-bold tracking-tight">{FLIGHT.registration}</div>
          </div>
          <div className="h-8 w-px bg-slate-200 dark:bg-slate-800" />
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              STD / ETD
            </div>
            <div className="text-lg font-bold tracking-tight">
              {FLIGHT.std} <span className="text-slate-400">/</span> {FLIGHT.etd}
            </div>
          </div>
        </div>

        <span
          className={`rounded-full px-4 py-1.5 text-xs font-extrabold tracking-widest ${
            badgeIsNeutral
              ? "bg-slate-500/15 text-slate-500 dark:text-slate-400"
              : isSecure
                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                : "bg-red-500/15 text-red-600 dark:text-red-400"
          }`}
        >
          {badgeLabel}
        </span>
      </header>

      {/* Main Content — 3 colunas */}
      <main className="grid min-h-0 flex-1 grid-cols-12 gap-4 overflow-hidden p-4">
        {/* Esquerda: Data Entry & Breakdown */}
        <div className="col-span-4 flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
          {error && (
            <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
              <strong className="font-semibold">Erro de cálculo: </strong>
              {error}
            </div>
          )}

          <SectionCard title="Combustível">
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-slate-400 dark:text-slate-500">Take-Off Fuel (kg)</label>
                <input
                  type="number"
                  min={0}
                  value={takeOffFuel}
                  onChange={(e) => setTakeOffFuel(Number(e.target.value))}
                  className="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-slate-400 dark:text-slate-500">Trip Fuel (kg)</label>
                <input
                  type="number"
                  min={0}
                  value={tripFuel}
                  onChange={(e) => setTripFuel(Number(e.target.value))}
                  className="rounded-md border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700"
                />
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Distribuição de Passageiros">
            <div className="flex flex-col gap-3">
              {cabinZones.map((zone) => (
                <div key={zone.code} className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium">{zone.label}</div>
                    <div className="text-[11px] text-slate-400 dark:text-slate-500">
                      Capacidade {zone.capacity}
                    </div>
                  </div>
                  <input
                    type="number"
                    min={0}
                    max={zone.capacity}
                    value={zone.pax}
                    onChange={(e) => updatePax(zone.code, Number(e.target.value))}
                    className="w-20 rounded-md border border-slate-300 bg-transparent px-2 py-1 text-right text-sm dark:border-slate-700"
                  />
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Carga / ULDs nos Porões">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">
                    <th className="pb-2 font-semibold">Posição</th>
                    <th className="pb-2 font-semibold">Tipo</th>
                    <th className="pb-2 pr-1 text-right font-semibold">Peso (kg)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {cargoRows.map((row, i) => (
                    <tr key={i}>
                      <td className="py-1.5 pr-2">
                        <input
                          value={row.position}
                          onChange={(e) => updateCargoRow(i, "position", e.target.value)}
                          className="w-16 rounded-md border border-slate-300 bg-transparent px-1.5 py-1 text-sm dark:border-slate-700"
                        />
                      </td>
                      <td className="py-1.5 pr-2">
                        <select
                          value={row.uldType}
                          onChange={(e) => updateCargoRow(i, "uldType", e.target.value)}
                          className="rounded-md border border-slate-300 bg-transparent px-1.5 py-1 text-sm dark:border-slate-700"
                        >
                          {ULD_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-1.5">
                        <input
                          type="number"
                          value={row.weight}
                          onChange={(e) => updateCargoRow(i, "weight", Number(e.target.value))}
                          className="w-24 rounded-md border border-slate-300 bg-transparent px-1.5 py-1 text-right text-sm dark:border-slate-700"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>

        {/* Centro: Weight Cascade */}
        <div className="col-span-4 flex min-h-0 flex-col overflow-y-auto pr-1">
          <SectionCard title="Weight Cascade">
            <div className="flex flex-col gap-5 py-1">
              <div className="flex flex-col gap-1">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  DOW
                </span>
                <span className="text-2xl font-bold tracking-tight">{formatKg(AIRCRAFT.dow)}</span>
                <span className="text-[11px] text-slate-400 dark:text-slate-500">DOI {AIRCRAFT.doi.toFixed(2)}</span>
              </div>

              <div className="flex justify-center text-slate-300 dark:text-slate-700">↓</div>

              <WeightGauge
                label="ZFW"
                actual={result?.zfw ?? AIRCRAFT.dow}
                limit={AIRCRAFT.mzfw}
              />

              <div className="flex justify-center text-slate-300 dark:text-slate-700">↓</div>

              <WeightGauge label="TOW" actual={towWeight} limit={AIRCRAFT.mtow} />

              <div className="flex justify-center text-slate-300 dark:text-slate-700">↓</div>

              <WeightGauge label="LDW" actual={ldwWeight} limit={AIRCRAFT.mlaw} />

              {result && (
                <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-500">
                  LIZFW {result.lizfw.toFixed(4)} · %MACZFW {result.mac_zfw.toFixed(2)}%
                </div>
              )}
            </div>
          </SectionCard>
        </div>

        {/* Direita: Visual Intelligence — Envelope de CG */}
        <div className="col-span-4 flex min-h-0 flex-col overflow-y-auto pr-1">
          <SectionCard title="CG Envelope">
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                  <CartesianGrid stroke="currentColor" strokeOpacity={0.08} />
                  <XAxis
                    dataKey="mac"
                    type="number"
                    domain={[10, 45]}
                    tick={{ fontSize: 11 }}
                    label={{ value: "%MAC / Index", position: "insideBottom", offset: -10, fontSize: 11 }}
                  />
                  <YAxis
                    dataKey="weight"
                    type="number"
                    domain={[100000, 240000]}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                    label={{ value: "Weight (kg)", angle: -90, position: "insideLeft", fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(value, name) =>
                      name === "weight" && typeof value === "number" ? formatKg(value) : value
                    }
                  />
                  <Line
                    data={ENVELOPE_POLYGON}
                    dataKey="weight"
                    stroke="#94a3b8"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                    name="Envelope"
                  />
                  {/* TOW/LDW: peso real (ou estimado a partir do combustível se
                      ainda não houver resposta), mas %MAC continua estimado —
                      o backend não calcula o efeito do combustível no índice. */}
                  <Scatter data={[towPoint, ldwPoint]} dataKey="weight" fill="#94a3b8" name="TOW/LDW (MAC estimado)" />
                  {/* ZFW é o único ponto totalmente real (peso e %MAC), vindo do /calculate */}
                  {zfwPoint && <Scatter data={[zfwPoint]} dataKey="weight" fill="#2563eb" name="ZFW" />}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-4 text-[11px] text-slate-500 dark:text-slate-400">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-blue-600" />
                ZFW (real)
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-slate-400" />
                TOW / LDW (%MAC estimado)
              </span>
            </div>
          </SectionCard>
        </div>
      </main>
    </div>
  );
}
