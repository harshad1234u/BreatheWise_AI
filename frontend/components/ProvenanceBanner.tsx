import React from 'react';
import { Radio, Database, AlertCircle, Clock, Info } from 'lucide-react';
import { NormalizedAirObservation } from '@/types/air-quality';

interface Props {
  observation: NormalizedAirObservation;
}

export const ProvenanceBanner: React.FC<Props> = ({ observation }) => {
  const {
    source_type,
    data_provider,
    observed_at,
    fetched_at,
    data_status,
    confidence_score,
    index_type,
    methodology_disclosure,
    locality_or_station,
  } = observation;

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' (' + d.toLocaleDateString() + ')';
    } catch {
      return isoString;
    }
  };

  const getSourceBadge = () => {
    switch (source_type) {
      case 'ground_station':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700">
            <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-600 dark:text-emerald-400" />
            <span>Live Ground Monitor Telemetry</span>
          </div>
        );
      case 'atmospheric_model':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-50 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300 border border-blue-300 dark:border-blue-700">
            <Database className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
            <span>Atmospheric Model Projection (CAMS)</span>
          </div>
        );
      case 'stale_cache':
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-50 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-700">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            <span>Stale Cached Observation</span>
          </div>
        );
      default:
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-rose-50 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-300 dark:border-rose-700">
            <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
            <span>Data Unavailable</span>
          </div>
        );
    }
  };

  const getIndexTypeBadge = () => {
    if (index_type === 'official_cpcb_naqi') {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-200">
          Official Indian NAQI
        </span>
      );
    } else if (index_type === 'indicative_particulate_subindex') {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200">
          Indicative Real-Time Sub-Index
        </span>
      );
    } else if (index_type === 'atmospheric_model_estimate') {
      return (
        <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-sky-100 text-sky-800 dark:bg-sky-900/60 dark:text-sky-200">
          Atmospheric Model Estimate
        </span>
      );
    }
    return null;
  };

  return (
    <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {getSourceBadge()}
          {getIndexTypeBadge()}
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
          <div className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            <span>Observed: {formatDate(observed_at)}</span>
          </div>
          <span className="hidden sm:inline">•</span>
          <div className="hidden sm:flex items-center gap-1">
            <span>Confidence: <strong className="capitalize text-slate-700 dark:text-slate-200">{confidence_score}</strong></span>
          </div>
        </div>
      </div>

      <div className="text-xs text-slate-600 dark:text-slate-300 flex items-start gap-2 pt-1 border-t border-slate-200 dark:border-slate-800">
        <Info className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
        <div>
          <span className="font-semibold text-slate-700 dark:text-slate-200">Provider & Provenance: </span>
          <span>{data_provider} {locality_or_station ? `(${locality_or_station})` : ''}</span>
          <p className="mt-1 text-slate-500 dark:text-slate-400 italic">
            {methodology_disclosure}
          </p>
        </div>
      </div>
    </div>
  );
};
