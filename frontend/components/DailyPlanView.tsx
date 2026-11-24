import React from 'react';
import { DailyPlanResponse, PlanRecommendation } from '@/types/plan';
import { Sparkles, ShieldCheck, Sun, CloudSun, Moon, Home, Leaf, ShieldAlert, AlertCircle } from 'lucide-react';

interface Props {
  plan: DailyPlanResponse;
}

export const DailyPlanView: React.FC<Props> = ({ plan }) => {
  const {
    ai_provider_used,
    is_fallback,
    safety_guidance,
    morning,
    afternoon,
    evening,
    indoor_air_suggestions,
    sustainable_alternatives,
    disclaimer,
    generated_at,
  } = plan;

  const getProviderBadge = () => {
    if (ai_provider_used === 'groq') {
      return (
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Synthesized by Groq Llama 3 (Primary AI)</span>
        </div>
      );
    } else if (ai_provider_used === 'gemini') {
      return (
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/30">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Synthesized by Google Gemini (Backup AI Failover)</span>
        </div>
      );
    } else {
      return (
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Deterministic Public-Health Engine (Zero-AI Fallback)</span>
        </div>
      );
    }
  };

  const renderPeriodRecommendations = (
    title: string,
    icon: React.ReactNode,
    recs: PlanRecommendation[]
  ) => {
    return (
      <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
        <div className="flex items-center gap-2 pb-2 border-b border-slate-100 dark:border-slate-800">
          <div className="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
            {icon}
          </div>
          <h3 className="font-bold text-sm text-slate-900 dark:text-white uppercase tracking-wider">
            {title}
          </h3>
        </div>

        <div className="space-y-3">
          {recs.map((rec, idx) => (
            <div
              key={idx}
              className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 space-y-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-bold text-xs text-slate-900 dark:text-white">
                  {rec.activity}
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                  {rec.time_window}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                    rec.location_type === 'indoor'
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                      : rec.location_type === 'outdoor'
                      ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                      : 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300'
                  }`}
                >
                  {rec.location_type}
                </span>

                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 capitalize">
                  Intensity: {rec.intensity}
                </span>

                <span className="text-[11px] text-slate-400">
                  Basis: {rec.data_context_used}
                </span>
              </div>

              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                {rec.explanation}
              </p>

              {rec.precautions && (
                <div className="flex items-start gap-1.5 p-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-200 border border-amber-200/80 dark:border-amber-900/40 text-[11px]">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                  <span>{rec.precautions}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Plan Header & Validation Metadata */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-extrabold text-lg text-slate-900 dark:text-white">
              Personalized Pollution-Aware Daily Schedule
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Synchronized with CPCB public-health constraints and Indian household dynamics
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {getProviderBadge()}
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Safety Guardrails Enforced</span>
          </div>
        </div>
      </div>

      {/* 3-Period Daily Routine */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {renderPeriodRecommendations('Morning Routine', <Sun className="w-4 h-4 text-amber-500" />, morning)}
        {renderPeriodRecommendations('Afternoon Routine', <CloudSun className="w-4 h-4 text-blue-500" />, afternoon)}
        {renderPeriodRecommendations('Evening Routine', <Moon className="w-4 h-4 text-indigo-500" />, evening)}
      </div>

      {/* Challenge Pillars 2 & 3: Indoor Intelligence & Sustainable Alternatives */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Indoor Air Intelligence Card */}
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 dark:border-slate-800">
            <div className="p-1.5 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400">
              <Home className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-sm text-slate-900 dark:text-white">
              Pillar 2: Indian Indoor Air Intelligence
            </h3>
          </div>

          <ul className="space-y-2.5 text-xs text-slate-600 dark:text-slate-300">
            {indoor_air_suggestions.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-500 mt-1.5 shrink-0" />
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Sustainable Lifestyle Alternatives Card */}
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 dark:border-slate-800">
            <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
              <Leaf className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-sm text-slate-900 dark:text-white">
              Pillar 3: Sustainable Mobility & Alternatives
            </h3>
          </div>

          <ul className="space-y-2.5 text-xs text-slate-600 dark:text-slate-300">
            {sustainable_alternatives.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Advisory Disclaimer */}
      <div className="p-3.5 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 flex items-start gap-2">
        <ShieldAlert className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
        <span>{disclaimer}</span>
      </div>
    </div>
  );
};
