import { ShieldWarning } from '@phosphor-icons/react';

export function BrandHero() {
  return (
    <div
      aria-hidden="true"
      className="relative w-full lg:w-5/12 bg-[#1b3b87] flex flex-col justify-between p-8 sm:p-10 lg:p-12 text-white overflow-hidden shrink-0 border-r border-[#142f70] select-none"
    >
      {/* Authentic Institutional Watermark Seal */}
      <img
        src="/lspu-logo.png"
        alt=""
        aria-hidden="true"
        className="absolute -right-20 -bottom-20 w-96 h-96 object-contain pointer-events-none opacity-[0.05] select-none"
      />

      <div className="relative z-10 flex flex-col gap-8">
        <div className="flex items-center gap-4 border-b border-white/10 pb-6">
          <img
            src="/lspu-logo.png"
            alt="Laguna State Polytechnic University Logo"
            className="w-16 h-16 lg:w-20 lg:h-20 object-contain shrink-0 drop-shadow-xs"
          />
          <div>
            <h1 className="text-xl lg:text-2xl font-bold tracking-tight text-white leading-snug">
              Laguna State
              <br />
              Polytechnic University
            </h1>
            <p className="text-xs font-semibold text-white/80 tracking-wider uppercase mt-1">
              Santa Cruz Campus
            </p>
          </div>
        </div>

        <div className="space-y-3 pt-1">
          <h2 className="text-sm font-bold text-[#f2c811] uppercase tracking-[0.12em]">
            EquipED Workspace
          </h2>
          <p className="text-white/80 text-sm leading-relaxed max-w-sm">
            An automated compliance workstation for Syllabus and Curriculum evaluations. Access is
            restricted to authorized faculty and administrative staff.
          </p>
        </div>
      </div>

      <div className="relative z-10 mt-16 lg:mt-0 flex items-start gap-3 border-t border-white/10 pt-6">
        <ShieldWarning
          className="size-4 shrink-0 text-[#f2c811] mt-0.5"
          aria-hidden="true"
        />
        <p className="text-white/80 text-[11px] font-medium max-w-sm leading-relaxed uppercase tracking-wider">
          Faculty Ledger System. Strictly for authorized institutional personnel. All access is
          monitored and logged.
        </p>
      </div>
    </div>
  );
}
