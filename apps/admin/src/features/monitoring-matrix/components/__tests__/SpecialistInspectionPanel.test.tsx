// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import React from 'react';
import { SpecialistInspectionPanel } from '../SpecialistInspectionPanel';
import type { EvaluationFlagItem, MasterSynthesisPillar } from '../../types';

afterEach(() => {
  cleanup();
});

describe('SpecialistInspectionPanel', () => {
  const mockPillar: MasterSynthesisPillar = {
    weight: 0.35,
    subtotal: 3.8,
    status: 'COMPLETED',
    criteria: [
      {
        criterion_id: 'SME-1',
        criterion_text: 'Topical and Technical Rigor',
        description: 'Depth of concurrency and memory virtualization principles',
        score: 4,
        justification: 'Exemplary coverage of thread synchronization primitives.',
        evidence: 'Section 3.2 diagrams accurately depict semaphore invariants.',
      },
    ],
    summary: 'Comprehensive pedagogical treatment of systems programming.',
    evaluator: {
      user_id: 'user-eval-sme',
      name: 'Dr. Evelyn Reed',
      email: 'evelyn.reed@university.edu',
      department: 'Systems Engineering',
    },
  };

  const mockFlags: EvaluationFlagItem[] = [
    {
      flag_id: 'flag-sme-12345678',
      evaluation_id: 'eval-1',
      agent_id: 'sme',
      severity: 'WARNING',
      criterion_id: 'SME-1',
      message: 'Potential outdated citation in chapter 4',
    },
    {
      flag_id: 'flag-other',
      evaluation_id: 'eval-1',
      agent_id: 'itso',
      severity: 'WARNING',
      message: 'ITSO flag',
    },
  ];

  it('renders tabpanel container with correct ARIA attributes and data-testid', () => {
    render(
      <SpecialistInspectionPanel
        activePillarId="sme"
        pillar={mockPillar}
        flags={mockFlags}
      />,
    );

    const panel = screen.getByRole('tabpanel');
    expect(panel.getAttribute('id')).toBe('tab-content-sme');
    expect(panel.getAttribute('aria-labelledby')).toBe('pillar-tab-sme');
    expect(panel.getAttribute('data-testid')).toBe('tab-content-sme');
    expect(panel.getAttribute('tabindex')).toBe('0');
  });

  it('renders specialist overview, score, evaluator, summary, criteria, and filtered flags', () => {
    render(
      <SpecialistInspectionPanel
        activePillarId="sme"
        pillar={mockPillar}
        flags={mockFlags}
      />,
    );

    const headings = screen.getAllByRole('heading', { level: 2, name: /content accuracy/i });
    expect(headings.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Subject Matter Expert (SME)')).toBeTruthy();
    expect(screen.getByText('3.80')).toBeTruthy();
    expect(screen.getByText(/evaluated by: dr\. evelyn reed/i)).toBeTruthy();
    expect(screen.getByText('Comprehensive pedagogical treatment of systems programming.')).toBeTruthy();

    // Rubric criteria
    expect(screen.getByText('Topical and Technical Rigor')).toBeTruthy();

    // Specialist flags (only active pillar flag rendered)
    expect(screen.getByText(/Specialist Compliance Flags \(1\)/)).toBeTruthy();
    expect(screen.getByText('Potential outdated citation in chapter 4')).toBeTruthy();
    expect(screen.queryByText('ITSO flag')).toBeNull();
  });

  it('renders awaiting specialist review when evaluator is absent', () => {
    const unreviewedPillar: MasterSynthesisPillar = {
      weight: 0.25,
      subtotal: null,
      status: 'PENDING',
      criteria: [],
      summary: '',
      evaluator: null,
    };

    render(
      <SpecialistInspectionPanel
        activePillarId="coordinator"
        pillar={unreviewedPillar}
      />,
    );

    expect(screen.getByText('Awaiting specialist review')).toBeTruthy();
    expect(screen.getByText('PENDING')).toBeTruthy();
    expect(screen.getByText('—')).toBeTruthy();
  });
});
