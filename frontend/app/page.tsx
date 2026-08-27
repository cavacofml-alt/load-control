"use client";

import { useState } from "react";
import { ApiError, calculateLoad, type CalculateResponse } from "@/lib/api";

const ULD_POSITIONS = [
  "11L",
  "11R",
  "11",
  "11P",
  "12L",
  "12R",
  "12",
  "12P",
  "21P",
  "CPT51",
];

const ULD_TYPES = ["AKE", "PKC", "PLA", "PAG", "PMC", "BULK"];

export default function Home() {
  const [registration, setRegistration] = useState("TC-JNH");
  const [positionCode, setPositionCode] = useState(ULD_POSITIONS[3]); // 11P
  const [uldType, setUldType] = useState(ULD_TYPES[4]); // PMC
  const [weight, setWeight] = useState("4800");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CalculateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await calculateLoad({
        registration,
        hold_loads: {
          [positionCode]: { uld_type: uldType, weight: Number(weight) },
        },
      });
      setResult(response);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`(${err.status}) ${err.message}`);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Erro desconhecido ao contactar a API.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-50 px-4 py-12 font-sans dark:bg-black">
      <main className="flex w-full max-w-xl flex-col gap-8">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight text-black dark:text-zinc-50">
            AWBS Load Control
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Simulador de carregamento — Weight &amp; Balance
          </p>
        </header>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4 rounded-lg border border-black/[.08] bg-white p-6 dark:border-white/[.145] dark:bg-zinc-950"
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="registration" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Matrícula
            </label>
            <input
              id="registration"
              type="text"
              value={registration}
              onChange={(e) => setRegistration(e.target.value)}
              className="rounded border border-black/[.08] bg-transparent px-3 py-2 text-sm text-black dark:border-white/[.145] dark:text-zinc-50"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1">
              <label htmlFor="position" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Posição
              </label>
              <select
                id="position"
                value={positionCode}
                onChange={(e) => setPositionCode(e.target.value)}
                className="rounded border border-black/[.08] bg-transparent px-3 py-2 text-sm text-black dark:border-white/[.145] dark:text-zinc-50"
              >
                {ULD_POSITIONS.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="uldType" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Tipo de ULD
              </label>
              <select
                id="uldType"
                value={uldType}
                onChange={(e) => setUldType(e.target.value)}
                className="rounded border border-black/[.08] bg-transparent px-3 py-2 text-sm text-black dark:border-white/[.145] dark:text-zinc-50"
              >
                {ULD_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="weight" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Peso (kg)
              </label>
              <input
                id="weight"
                type="number"
                min="0"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                className="rounded border border-black/[.08] bg-transparent px-3 py-2 text-sm text-black dark:border-white/[.145] dark:text-zinc-50"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-2 flex h-11 items-center justify-center rounded-full bg-foreground px-5 text-sm font-medium text-background transition-colors hover:bg-[#383838] disabled:opacity-50 dark:hover:bg-[#ccc]"
          >
            {loading ? "A calcular..." : "Calculate Load"}
          </button>
        </form>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
            <strong className="font-semibold">Erro de validação: </strong>
            {error}
          </div>
        )}

        {result && (
          <div className="rounded-lg border border-black/[.08] bg-white p-6 dark:border-white/[.145] dark:bg-zinc-950">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Resultado
            </h2>
            <dl className="grid grid-cols-2 gap-4">
              <ResultItem label="ZFW" value={`${result.zfw.toLocaleString()} kg`} />
              <ResultItem label="LIZFW" value={result.lizfw.toString()} />
              <ResultItem label="%MAC ZFW" value={`${result.mac_zfw}%`} />
              <ResultItem
                label="Dentro dos limites"
                value={result.zfw_within_limits ? "Sim" : "Não"}
                highlight={!result.zfw_within_limits}
              />
            </dl>
          </div>
        )}
      </main>
    </div>
  );
}

function ResultItem({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd
        className={`text-lg font-medium ${
          highlight ? "text-red-600 dark:text-red-400" : "text-black dark:text-zinc-50"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
