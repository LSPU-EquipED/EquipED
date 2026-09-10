// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { UseQueryResult } from '@tanstack/react-query';
import React from 'react';
import { MasterSynthesisPage } from '../MasterSynthesisPage';
import * as useMasterSynthesisDetailModule from '../../hooks/useMasterSynthesisDetail';
import type { MasterSynthesisDetailResponse } from '../../types';

const mockNavigate = vi.fn();

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ documentId: 'doc-456' }),
  Link: ({
    to,
    children,
    className,
  }: {
    to: string;
    children?: React.ReactNode;
    className?: string;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

const mockSynthesisDetail: MasterSynthesisDetailResponse = {
  document_id: 'doc-456',
  document_title: 'Advanced Operating Systems Module',
  course_code: 'CS401',
  program: 'BSCS',
  author: {
    user_id: 'user-author-1',
    name: 'Dr. Alan Turing',
    email: 'alan.turing@university.edu',
    department: 'Department of Computer Science',
  },
  synthesized_score: 3.65,
  adjectival_rating: 'Very Satisfactory',
  evaluation_status: 'COMPLETED',
  last_updated: '2026-06-01T14:30:00Z',
  pillars: {
    sme: {
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
    },
    coordinator: {
      weight: 0.30,
      subtotal: 3.5,
      status: 'COMPLETED',
      criteria: [
        {
          criterion_id: 'PC-1',
          criterion_text: 'Syllabus Alignment & Credit Hours',
          description: 'Topic mapping matches 14-week curriculum schedule',
          score: 3,
          justification: 'Aligned well with CLO 2 and CLO 4.',
          evidence: 'Module syllabus mapping table in Appendix B.',
        },
      ],
      summary: 'Meets program requirements with solid schedule alignment.',
      evaluator: {
        user_id: 'user-eval-pc',
        name: 'Prof. Marcus Vance',
        email: 'marcus.vance@university.edu',
        department: 'Computer Science Curriculum Committee',
      },
    },
    gad: {
      weight: 0.20,
      subtotal: 3.7,
      status: 'COMPLETED',
      criteria: [
        {
          criterion_id: 'GAD-1',
          criterion_text: 'Gender-Fair Language & Inclusivity',
          description: 'Non-discriminatory framing and diverse examples',
          score: 4,
          justification: 'Adheres strictly to CHED GAD guidelines.',
          evidence: 'Equal gender representation in historical case studies.',
        },
      ],
      summary: 'Excellent adherence to inclusive curriculum guidelines.',
      evaluator: {
        user_id: 'user-eval-gad',
        name: 'Dr. Patricia Chen',
        email: 'patricia.chen@university.edu',
        department: 'Gender and Development Focal Point',
      },
    },
    itso: {
      weight: 0.15,
      subtotal: 3.4,
      status: 'COMPLETED',
      criteria: [
        {
          criterion_id: 'ITSO-1',
          criterion_text: 'Copyright & Citation Integrity',
          description: 'Attribution for third-party figures and open-source licenses',
          score: 3,
          justification: 'All diagram licenses verified with attribution footnotes.',
          evidence: 'Creative Commons CC-BY attribution noted on page 14.',
        },
      ],
      summary: 'IP and citation compliance verified with minor formatting notes.',
      evaluator: {
        user_id: 'user-eval-itso',
        name: 'Atty. Sofia Ramos',
        email: 'sofia.ramos@university.edu',
        department: 'Innovation & Technology Support Office',
      },
    },
  },
  flags: [
    {
      flag_id: 'flag-101',
      evaluation_id: 'eval-456',
      agent_id: 'itso',
      criterion_id: 'ITSO-1',
      criterion_text: 'Copyright & Citation Integrity',
      score: 3,
      justification: 'Verify license badge resolution on diagram 4',
      chunk_id: null,
      message: 'License icon slightly low resolution in print view',
    },
  ],
  can_certify: true,
};

describe('MasterSynthesisPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders loading skeleton when detail is loading', () => {
    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    expect(screen.getByTestId('master-synthesis-loading')).toBeDefined();
  });

  it('renders error state with retry and back link on failure', () => {
    const mockRefetch = vi.fn();
    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch: mockRefetch,
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    expect(screen.getByTestId('master-synthesis-error')).toBeDefined();
    expect(screen.getByText(/Unable to Load Master Synthesis Scorecard/i)).toBeDefined();

    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(mockRefetch).toHaveBeenCalled();
  });

  it('renders executive header with document metadata and course details', () => {
    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: mockSynthesisDetail,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    expect(screen.getByText('Advanced Operating Systems Module')).toBeDefined();
    expect(screen.getByText('BSCS')).toBeDefined();
    expect(screen.getByText('Course: CS401')).toBeDefined();
    expect(screen.getAllByText('COMPLETED').length).toBeGreaterThanOrEqual(1);
  });

  it('renders composite score banner with rating and pillar convergence progress pill', () => {
    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: mockSynthesisDetail,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    const banner = screen.getByTestId('composite-score-banner');
    expect(banner).toBeDefined();
    expect(screen.getByText('3.65')).toBeDefined();
    expect(screen.getAllByText(/\/ 4.00/).length).toBeGreaterThan(0);
    expect(screen.getByText('Very Satisfactory')).toBeDefined();
    expect(screen.getByTestId('pillar-progress-pill').textContent).toContain('4/4 Pillars Complete');
  });

  it('renders 4-pillar executive strip with evaluator signature chips', () => {
    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: mockSynthesisDetail,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    const strip = screen.getByTestId('four-pillar-executive-strip');
    expect(strip).toBeDefined();

    // 4 domain cards
    expect(screen.getByTestId('pillar-card-sme')).toBeDefined();
    expect(screen.getByTestId('pillar-card-coordinator')).toBeDefined();
    expect(screen.getByTestId('pillar-card-gad')).toBeDefined();
    expect(screen.getByTestId('pillar-card-itso')).toBeDefined();

    // Evaluator signature chips
    expect(screen.getByTestId('evaluator-chip-sme')).toBeDefined();
    expect(screen.getAllByText(/Evaluated by: Dr. Evelyn Reed/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Evaluated by: Prof. Marcus Vance/i)).toBeDefined();
    expect(screen.getByText(/Evaluated by: Dr. Patricia Chen/i)).toBeDefined();
    expect(screen.getByText(/Evaluated by: Atty. Sofia Ramos/i)).toBeDefined();
  });

  it('displays awaiting review chip when a pillar is not yet evaluated', () => {
    const partialData: MasterSynthesisDetailResponse = {
      ...mockSynthesisDetail,
      synthesized_score: null,
      adjectival_rating: null,
      can_certify: false,
      pillars: {
        ...mockSynthesisDetail.pillars,
        itso: {
          weight: 0.15,
          subtotal: null,
          status: 'PENDING',
          criteria: [],
          summary: '',
          evaluator: null,
        },
      },
    };

    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: partialData,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    expect(screen.getByTestId('awaiting-review-itso')).toBeDefined();
    expect(screen.getByTestId('pillar-progress-pill').textContent).toContain('3/4 Pillars Complete');
  });

  it('supports tabbed pillar inspection to view criteria, justification, evidence, and flags', () => {
    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: mockSynthesisDetail,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    // Default active tab is SME
    expect(screen.getByTestId('tab-content-sme')).toBeDefined();
    expect(screen.getByText('Topical and Technical Rigor')).toBeDefined();
    expect(screen.getByText('Exemplary coverage of thread synchronization primitives.')).toBeDefined();
    expect(screen.getByText('"Section 3.2 diagrams accurately depict semaphore invariants."')).toBeDefined();

    // Switch to ITSO tab
    const itsoTabBtn = screen.getByTestId('tab-button-itso');
    fireEvent.click(itsoTabBtn);

    expect(screen.getByTestId('tab-content-itso')).toBeDefined();
    expect(screen.getByText('Copyright & Citation Integrity')).toBeDefined();
    expect(screen.getByText('All diagram licenses verified with attribution footnotes.')).toBeDefined();

    // Verify ITSO flag is displayed
    expect(screen.getByText(/License icon slightly low resolution in print view/i)).toBeDefined();
  });

  it('renders accreditation signatory block and certifies when can_certify is true', () => {
    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: mockSynthesisDetail,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    const signatoryBlock = screen.getByTestId('accreditation-signatory-block');
    expect(signatoryBlock).toBeDefined();
    expect(screen.getByText(/Director, Center for Instructional Development/i)).toBeDefined();

    const certifyBtn = screen.getByTestId('certify-button');
    expect(certifyBtn).toBeDefined();
    expect(certifyBtn.getAttribute('disabled')).toBeNull();

    fireEvent.click(certifyBtn);
    expect(screen.getByText(/Certified for Accreditation/i)).toBeDefined();
  });

  it('triggers window.print when Export Accreditation PDF button is clicked', () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {});

    vi.spyOn(useMasterSynthesisDetailModule, 'useMasterSynthesisDetail').mockReturnValue({
      data: mockSynthesisDetail,
      isLoading: false,
      isError: false,
    } as unknown as UseQueryResult<MasterSynthesisDetailResponse, Error>);

    render(<MasterSynthesisPage />);

    const exportBtn = screen.getByTestId('export-pdf-button');
    expect(exportBtn).toBeDefined();

    fireEvent.click(exportBtn);
    expect(printSpy).toHaveBeenCalled();
    printSpy.mockRestore();
  });
});
