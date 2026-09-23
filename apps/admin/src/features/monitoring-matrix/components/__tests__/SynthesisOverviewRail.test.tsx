// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { SynthesisOverviewRail } from '../SynthesisOverviewRail';
import type { MasterSynthesisDetailResponse } from '../../types';

afterEach(() => {
  cleanup();
});

function createMockDetail(
  overrides?: Partial<MasterSynthesisDetailResponse>,
): MasterSynthesisDetailResponse {
  return {
    document_id: 'doc-123',
    document_title: 'Syllabus Review',
    course_code: 'ENG101',
    program: 'AB-ENG',
    author: {
      user_id: 'u-auth',
      name: 'Author Name',
      email: 'author@uni.edu',
      department: 'English',
    },
    synthesized_score: 88.5,
    adjectival_rating: 'Satisfactory',
    evaluation_status: 'COMPLETED',
    last_updated: '2026-06-01T12:00:00Z',
    can_certify: false,
    flags: [],
    pillars: {
      sme: {
        weight: 0.35,
        subtotal: 3.5,
        status: 'COMPLETED',
        criteria: [],
        summary: 'SME complete',
        evaluator: {
          user_id: 'u-sme',
          name: 'Dr. Jane SME',
          email: 'sme@uni.edu',
          department: 'English Dept',
        },
      },
      coordinator: {
        weight: 0.3,
        subtotal: 3.2,
        status: 'COMPLETED',
        criteria: [],
        summary: 'Coord complete',
        evaluator: {
          user_id: 'u-coord',
          name: 'Prof. Mark Coord',
          email: 'coord@uni.edu',
          department: 'Curriculum',
        },
      },
      gad: {
        weight: 0.2,
        subtotal: null,
        status: 'PENDING',
        criteria: [],
        summary: '',
        evaluator: null,
      },
      itso: {
        weight: 0.15,
        subtotal: null,
        status: 'PENDING',
        criteria: [],
        summary: '',
        evaluator: null,
      },
    },
    ...overrides,
  };
}

describe('SynthesisOverviewRail', () => {
  it('renders composite score, convergence progress, and clearance block', () => {
    const data = createMockDetail();
    render(
      <SynthesisOverviewRail
        data={data}
        activePillarId="sme"
        onSelectPillar={vi.fn()}
      />,
    );

    expect(screen.getByTestId('composite-score-banner')).toBeDefined();
    expect(screen.getByText('88.50%')).toBeDefined();
    expect(screen.getByText('Satisfactory')).toBeDefined();
    expect(screen.getByTestId('pillar-progress-pill').textContent).toContain('2/4 Pillars Complete');
    expect(screen.getByTestId('accreditation-signatory-block')).toBeDefined();
    expect(screen.getByTestId('certify-readiness-indicator').textContent).toContain('Awaiting 4/4 Verification');
  });

  it('displays non-default pillar weights derived dynamically from response data', () => {
    const data = createMockDetail({
      pillars: {
        sme: {
          weight: 0.5,
          subtotal: 3.9,
          status: 'COMPLETED',
          criteria: [],
          summary: '',
          evaluator: null,
        },
        coordinator: {
          weight: 0.25,
          subtotal: 3.1,
          status: 'COMPLETED',
          criteria: [],
          summary: '',
          evaluator: null,
        },
        gad: {
          weight: 0.15,
          subtotal: 3.0,
          status: 'COMPLETED',
          criteria: [],
          summary: '',
          evaluator: null,
        },
        itso: {
          weight: 0.1,
          subtotal: 3.0,
          status: 'COMPLETED',
          criteria: [],
          summary: '',
          evaluator: null,
        },
      },
    });

    render(
      <SynthesisOverviewRail
        data={data}
        activePillarId="sme"
        onSelectPillar={vi.fn()}
      />,
    );

    const smeTab = screen.getByTestId('pillar-card-sme');
    expect(smeTab.textContent).toContain('50% weight');

    const coordTab = screen.getByTestId('pillar-card-coordinator');
    expect(coordTab.textContent).toContain('25% weight');

    const gadTab = screen.getByTestId('pillar-card-gad');
    expect(gadTab.textContent).toContain('15% weight');

    const itsoTab = screen.getByTestId('pillar-card-itso');
    expect(itsoTab.textContent).toContain('10% weight');
  });

  it('handles missing weight gracefully as Unknown', () => {
    const data = createMockDetail({
      pillars: {
        sme: {
          // @ts-expect-error testing missing weight
          weight: undefined,
          subtotal: 3.5,
          status: 'COMPLETED',
          criteria: [],
          summary: '',
          evaluator: null,
        },
      },
    });

    render(
      <SynthesisOverviewRail
        data={data}
        activePillarId="sme"
        onSelectPillar={vi.fn()}
      />,
    );

    const smeTab = screen.getByTestId('pillar-card-sme');
    expect(smeTab.textContent).toContain('Unknown weight');
  });

  it('handles keyboard navigation and tab selection callbacks', () => {
    const onSelectPillar = vi.fn();
    const data = createMockDetail();

    render(
      <SynthesisOverviewRail
        data={data}
        activePillarId="sme"
        onSelectPillar={onSelectPillar}
      />,
    );

    const smeTab = screen.getByTestId('pillar-card-sme');
    const coordTab = screen.getByTestId('pillar-card-coordinator');

    // Click selection
    fireEvent.click(coordTab);
    expect(onSelectPillar).toHaveBeenCalledWith('coordinator');

    // Arrow down key navigation from SME
    fireEvent.keyDown(smeTab, { key: 'ArrowDown' });
    expect(onSelectPillar).toHaveBeenCalledWith('coordinator');

    // Arrow up key wraps to last item
    fireEvent.keyDown(smeTab, { key: 'ArrowUp' });
    expect(onSelectPillar).toHaveBeenCalledWith('itso');

    // End key jumps to last
    fireEvent.keyDown(smeTab, { key: 'End' });
    expect(onSelectPillar).toHaveBeenCalledWith('itso');

    // Home key jumps to first
    fireEvent.keyDown(coordTab, { key: 'Home' });
    expect(onSelectPillar).toHaveBeenCalledWith('sme');
  });

  it('reflects can_certify clearance state', () => {
    const data = createMockDetail({
      can_certify: true,
      pillars: {
        sme: { weight: 0.25, subtotal: 4, status: 'COMPLETED', criteria: [], summary: '', evaluator: null },
        coordinator: { weight: 0.25, subtotal: 4, status: 'COMPLETED', criteria: [], summary: '', evaluator: null },
        gad: { weight: 0.25, subtotal: 4, status: 'COMPLETED', criteria: [], summary: '', evaluator: null },
        itso: { weight: 0.25, subtotal: 4, status: 'COMPLETED', criteria: [], summary: '', evaluator: null },
      },
    });

    render(
      <SynthesisOverviewRail
        data={data}
        activePillarId="sme"
        onSelectPillar={vi.fn()}
      />,
    );

    expect(screen.getByText('Ready for Sign-off')).toBeDefined();
    expect(screen.getByTestId('certify-readiness-indicator').textContent).toContain(
      'Accreditation Sign-off Ready (Read-only)',
    );
  });
});
