import React from 'react';
import { Wind, ShieldCheck, Activity } from 'lucide-react';

export const Navbar: React.FC = () => {
  return (
    <header className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-teal-500 to-emerald-400 flex items-center justify-center text-white shadow-md shadow-teal-500/20">
            <Wind className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-xl tracking-tight text-slate-900 dark:text-white">
                BreatheWise<span className="text-teal-600 dark:text-teal-400"> AI</span>
              </span>
              <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-teal-50 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                v1.2 Baseline
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 hidden sm:block">
              Urban Air Quality Assistant & Public-Health Decision Engine
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-medium text-slate-600 dark:text-slate-300">
          <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span>Official CPCB Breakpoint Engine</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <Activity className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-pulse motion-reduce:animate-none" aria-hidden="true" />
            <span>3-Tier Telemetry</span>
          </div>
        </div>
      </div>
    </header>
  );
};
