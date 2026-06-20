import { ShieldAlert } from 'lucide-react';

export function BrandHero() {
  return (
    <div
      aria-hidden="true"
      className="relative w-full lg:w-5/12 bg-primary flex flex-col justify-between p-8 lg:p-12 text-primary-foreground overflow-hidden shrink-0 border-r border-primary-foreground/20"
    >
      {/* Subtle Academic Grid Pattern overlay for texture */}
      <div
        className="absolute inset-0 opacity-[0.08] pointer-events-none mix-blend-overlay"
        style={{
          backgroundImage: `linear-gradient(rgba(255, 255, 255, 1) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 1) 1px, transparent 1px)`,
          backgroundSize: '32px 32px',
        }}
      />

      <div className="relative z-10 flex flex-col gap-8">
        <div className="flex items-center gap-4 border-b border-primary-foreground/10 pb-6">
          <img
            src="/lspu-logo.png"
            alt="Laguna State Polytechnic University Logo"
            className="w-16 h-16 lg:w-20 lg:h-20 object-contain shrink-0"
          />
          <div>
            <h1 className="text-xl lg:text-2xl font-bold tracking-tight text-primary-foreground leading-snug">
              Laguna State
              <br />
              Polytechnic University
            </h1>
            <p className="text-xs font-semibold text-primary-foreground/80 tracking-wider uppercase mt-1">
              Santa Cruz Campus
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <h2 className="text-lg font-bold text-primary-foreground uppercase tracking-wider">
            EquipED Workspace
          </h2>
          <p className="text-primary-foreground/70 text-sm leading-relaxed max-w-sm">
            An automated compliance workstation for Syllabus and Curriculum evaluations. Access is
            restricted to authorized faculty and administrative staff.
          </p>
        </div>
      </div>

      <div className="relative z-10 mt-16 lg:mt-0 flex items-start gap-3 border-t border-primary-foreground/10 pt-6">
        <ShieldAlert
          className="size-4 shrink-0 text-primary-foreground/80 mt-0.5"
          aria-hidden="true"
        />
        <p className="text-primary-foreground/80 text-xs font-medium max-w-sm leading-relaxed uppercase tracking-wider">
          Faculty Ledger System. Strictly for authorized institutional personnel. All access is
          monitored and logged.
        </p>
      </div>
    </div>
  );
}
