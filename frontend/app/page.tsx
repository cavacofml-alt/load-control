"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, listFlights, type Flight } from "@/lib/api";

const STATUS_STYLES: Record<Flight["status"], string> = {
  SCHEDULED: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  CLOSED: "bg-slate-500/15 text-slate-500 dark:text-slate-400",
  DEPARTED: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  CANCELLED: "bg-red-500/15 text-red-600 dark:text-red-400",
};

function formatStd(std: string) {
  const date = new Date(std);
  if (Number.isNaN(date.getTime())) return std;
  return `${date.toLocaleDateString("pt-PT")} ${date.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" })}Z`;
}

export default function FlightListPage() {
  const [flights, setFlights] = useState<Flight[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listFlights()
      .then((data) => {
        if (!cancelled) setFlights(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? `(${err.status}) ${err.message}` : "Falha ao contactar a API.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white px-6 py-4 dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-lg font-bold tracking-tight">AWBS · Voos</h1>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Selecione um voo para calcular a carga e, quando pronto, assinar a loadsheet.
        </p>
      </header>

      <main className="mx-auto max-w-4xl p-6">
        {error && (
          <div className="mb-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
            <strong className="font-semibold">Erro: </strong>
            {error}
          </div>
        )}

        {flights === null && !error && (
          <p className="text-sm text-slate-400 dark:text-slate-500">A carregar voos…</p>
        )}

        {flights !== null && flights.length === 0 && (
          <p className="text-sm text-slate-400 dark:text-slate-500">Sem voos registados.</p>
        )}

        {flights !== null && flights.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-[11px] uppercase tracking-wide text-slate-400 dark:border-slate-800 dark:text-slate-500">
                  <th className="px-4 py-3 font-semibold">Voo</th>
                  <th className="px-4 py-3 font-semibold">Rota</th>
                  <th className="px-4 py-3 font-semibold">STD</th>
                  <th className="px-4 py-3 font-semibold">Matrícula</th>
                  <th className="px-4 py-3 font-semibold">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {flights.map((flight) => (
                  <tr key={flight.id}>
                    <td className="px-4 py-3 font-semibold">
                      <Link href={`/flights/${flight.id}`} className="hover:underline">
                        {flight.flight_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      {flight.origin}-{flight.destination}
                    </td>
                    <td className="px-4 py-3">{formatStd(flight.std)}</td>
                    <td className="px-4 py-3">{flight.aircraft_registration ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold tracking-wide ${STATUS_STYLES[flight.status]}`}>
                        {flight.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
