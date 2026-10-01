import { equipedLogoReversedUrl, lspuLogoUrl } from '@equiped/ui';
import '../styles/brand-hero.css';

export function BrandHero() {
  return (
    <aside aria-label="About EquipED" className="auth-brand-panel">
      <div className="auth-brand-product">
        <img
          src={equipedLogoReversedUrl}
          alt="EquipED Workspace"
          width={304}
          height={88}
          className="auth-brand-logo"
        />
      </div>

      <div className="auth-brand-purpose">
        <h2>Review your learning materials.</h2>
        <p>
          Evaluate your modules against institutional rubrics and reference
          documents.
        </p>
      </div>

      <div className="auth-brand-institution">
        <img
          src={lspuLogoUrl}
          alt="Laguna State Polytechnic University"
          width={36}
          height={36}
          className="auth-brand-emblem"
        />
        <div>
          <p>Laguna State Polytechnic University</p>
          <span>Santa Cruz Campus</span>
        </div>
      </div>
    </aside>
  );
}
