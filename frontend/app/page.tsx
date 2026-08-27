"use client";

import { useState } from "react";
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

// ---------------------------------------------------------------------------
// Mock data — valores estáticos realistas para o scaffold visual (Fase de UI).
// Não vem da API ainda; ver lib/api.ts para a integração real do /calculate.
// ---------------------------------------------------------------------------

const FLIGHT = {
  route: "FRA-FAO",
  registration: "TC-JNH",
  std: "14:35Z",
  etd: "14:50Z",
};

const AIRCRAFT = {
  dow: 115000,
  doi: 52.0,
  mzfw: 175000,
  mtow: 233000,
  mlaw: 187000,
};

const WEIGHTS = [
  { key: "zfw", label: "ZFW", actual: 158200, limit: AIRCRAFT.mzfw },
  { key: "tow", label: "TOW", actual: 210400, limit: AIRCRAFT.mtow },
  { key: "ldw", label: "LDW", actual: 179800, limit: AIRCRAFT.mlaw },
];

const ALL_WITHIN_LIMITS = WEIGHTS.every((w) => w.actual <= w.limit);

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

// Envelope de CG (polígono fechado) e os 3 pontos de ZFW/TOW/LDW — forma
// ilustrativa, não os limites reais certificados do A330-300.
const ENVELOPE_POLYGON = [
  { mac: 18, weight: 110000 },
  { mac: 15, weight: 175000 },
  { mac: 24, weight: 233000 },
  { mac: 38, weight: 233000 },
  { mac: 34, weight: 175000 },
  { mac: 28, weight: 110000 },
  { mac: 18, weight: 110000 },
];

const CG_POINTS = [
  { mac: 24.1, weight: WEIGHTS[0].actual, label: "ZFW" },
  { mac: 27.4, weight: WEIGHTS[1].actual, label: "TOW" },
  { mac: 25.8, weight: WEIGHTS[2].actual, label: "LDW" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatKg(value: number) {
  return `${value.toLocaleString("en-US")} kg`;
}

function gaugeColor(ratio: number) {
  if (ratio >= 1) return "bg-red-500";
  if (ratio >= 0.92) return "bg-amber-500";
  return "bg-emerald-500";
}

function WeightGauge({ label, actual, limit }: { label: string; actual: number; limit: number }) {
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

  function updatePax(code: string, pax: number) {
    setCabinZones((zones) => zones.map((z) => (z.code === code ? { ...z, pax } : z)));
  }

  function updateCargoRow(index: number, field: "position" | "uldType" | "weight", value: string | number) {
    setCargoRows((rows) => rows.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  }

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
            ALL_WITHIN_LIMITS
              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
              : "bg-red-500/15 text-red-600 dark:text-red-400"
          }`}
        >
          {ALL_WITHIN_LIMITS ? "FLIGHT SECURE" : "OUT OF LIMITS"}
        </span>
      </header>

      {/* Main Content — 3 colunas */}
      <main className="grid min-h-0 flex-1 grid-cols-12 gap-4 overflow-hidden p-4">
        {/* Esquerda: Data Entry & Breakdown */}
        <div className="col-span-4 flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
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

              {WEIGHTS.map((w) => (
                <div key={w.key} className="flex flex-col gap-2">
                  <WeightGauge label={w.label} actual={w.actual} limit={w.limit} />
                  {w.key !== "ldw" && <div className="flex justify-center text-slate-300 dark:text-slate-700">↓</div>}
                </div>
              ))}
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
                  <Scatter data={CG_POINTS} dataKey="weight" fill="#2563eb" name="Pontos" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-4 text-[11px] text-slate-500 dark:text-slate-400">
              {CG_POINTS.map((p) => (
                <span key={p.label} className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-blue-600" />
                  {p.label}
                </span>
              ))}
            </div>
          </SectionCard>
        </div>
      </main>
    </div>
  );
}
