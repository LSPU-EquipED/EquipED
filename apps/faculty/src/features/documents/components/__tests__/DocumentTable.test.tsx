// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { ComponentProps, ReactNode } from 'react';
import type { ClientDocument, LatestEvaluationItem } from '@equiped/types';
import { DocumentTable, DocumentTableSkeleton } from '../DocumentTable';

vi.mock('@tanstack/react-router', () => ({
  Link: ({ to, children, ...props }: { to: string; children?: ReactNode }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));
afterEach(cleanup);

const sampleDocuments: ClientDocument[] = [
  {
    documentId: 'doc-1',
    title: 'Data Structures SLM',
    courseTitle: 'CS 101 - Data Structures',
    lessonTitle: 'Module 1',
    academicYear: '2025-2026',
    courseCode: 'CS101',
    pageCount: 15,
    hasOcrPages: false,
    chunks: [],
    program: 'BSCS',
    sourceType: 'slm',
    uploadedAt: '2026-08-15T10:00:00Z',
    processingStatus: 'PROCESSED',
  },
  {
    documentId: 'doc-2',
    title: 'Intro to IT Module',
    courseTitle: 'IT 101 - Intro to IT',
    lessonTitle: 'Module 2',
    academicYear: '2025-2026',
    courseCode: 'IT101',
    pageCount: 20,
    hasOcrPages: false,
    chunks: [],
    program: 'BSInfoTech',
    sourceType: 'slm',
    uploadedAt: '2026-08-16T11:00:00Z',
    processingStatus: 'PENDING',
  },
  {
    documentId: 'doc-3',
    title: 'Failed Upload Module',
    courseTitle: 'CS 202 - Algorithms',
    lessonTitle: 'Module 3',
    academicYear: '2025-2026',
    courseCode: 'CS202',
    pageCount: 5,
    hasOcrPages: false,
    chunks: [],
    program: 'BSCS',
    sourceType: 'slm',
    uploadedAt: '2026-08-17T12:00:00Z',
    processingStatus: 'FAILED',
  },
];

function renderTable(props: Partial<ComponentProps<typeof DocumentTable>> = {}) {
  return render(
    <DocumentTable
      documents={sampleDocuments}
      flashId={null}
      latestEvalsState={{ isSuccess: true }}
      {...props}
    />,
  );
}

function openActions(title = sampleDocuments[0].title) {
  fireEvent.click(screen.getByRole('button', { name: `Actions for ${title}` }));
}

describe('DocumentTable', () => {
  it('keeps column semantics and shows only a three-dot action trigger per row', () => {
    renderTable();
    const headers = screen.getAllByRole('columnheader');
    expect(headers).toHaveLength(6);
    headers.forEach((header) => expect(header.getAttribute('scope')).toBe('col'));
    expect(screen.getByText('Module Name')).toBeDefined();
    expect(screen.getByText('Actions')).toBeDefined();
    expect(screen.getAllByRole('button', { name: /actions for/i })).toHaveLength(3);
    expect(screen.queryByRole('menu')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('keeps the Type column for a mixed document inventory', () => {
    renderTable({
      documents: [
        ...sampleDocuments,
        {
          ...sampleDocuments[0],
          documentId: 'syllabus-1',
          sourceType: 'syllabus',
        },
      ],
    });
    expect(screen.getAllByRole('columnheader')).toHaveLength(7);
    expect(screen.getByText('Type')).toBeDefined();
  });

  it('offers the ready specialist workspace inside the menu', () => {
    renderTable({ documents: [sampleDocuments[0]] });
    expect(screen.getByText('Ready to Evaluate')).toBeDefined();
    openActions();
    const evaluate = screen.getByRole('menuitem', {
      name: 'Start evaluation for Data Structures SLM',
    });
    expect(evaluate.getAttribute('href')).toBe('/specialists/sme/doc-1');
    expect(evaluate.textContent).toBe('Evaluate');
  });

  it.each([
    ['COMPLETED_PARTIAL', 'Evaluated', 'Open evaluation for Data Structures SLM'],
    ['EVALUATING', 'Evaluating', 'View evaluation progress for Data Structures SLM'],
    ['FAILED', 'Evaluation Failed', 'Inspect evaluation for Data Structures SLM'],
  ])('preserves the %s evaluation action and its specialist destination', (status, badge, name) => {
    const latest: LatestEvaluationItem = {
      document_id: 'doc-1',
      evaluation_id: 'evaluation-1',
      status,
      target_agent: 'sme',
      submitted_at: '2026-08-20T10:00:00Z',
    };
    renderTable({ documents: [sampleDocuments[0]], latestEvalsByDocId: { 'doc-1': latest } });
    expect(screen.getByText(badge)).toBeDefined();
    openActions();
    expect(screen.getByRole('menuitem', { name }).getAttribute('href')).toBe(
      '/specialists/sme/doc-1',
    );
  });

  it('preserves the historical all-specialist result destination', () => {
    renderTable({
      documents: [sampleDocuments[0]],
      latestEvalsByDocId: {
        'doc-1': {
          document_id: 'doc-1',
          evaluation_id: 'all-result',
          status: 'COMPLETED',
          target_agent: 'all',
          submitted_at: '2026-08-20T10:00:00Z',
        },
      },
    });
    openActions();
    expect(
      screen
        .getByRole('menuitem', { name: 'Open evaluation for Data Structures SLM' })
        .getAttribute('href'),
    ).toBe('/evaluations/all-result');
  });

  it.each([
    [sampleDocuments[0], { isLoading: true }, 'Checking Status'],
    [sampleDocuments[0], { isError: true }, 'Status Unavailable'],
    [sampleDocuments[1], { isSuccess: true }, 'Processing'],
    [sampleDocuments[2], { isSuccess: true }, 'Upload Failed'],
  ])('does not offer evaluation when the module state is %s', (document, state, badge) => {
    const inspect = vi.fn();
    renderTable({ documents: [document], latestEvalsState: state, onInspect: inspect });
    expect(screen.getByText(badge)).toBeDefined();
    openActions(document.title);
    expect(screen.getAllByRole('menuitem')).toHaveLength(2);
    expect(screen.getByRole('menuitem', { name: `Open ${document.title} PDF` })).toBeDefined();
    fireEvent.click(screen.getByRole('menuitem', { name: 'View details' }));
    expect(inspect).toHaveBeenCalledOnce();
    expect(inspect).toHaveBeenCalledWith(document);
  });

  it('opens the PDF in a separate tab and opens module details only through the menu', () => {
    const inspect = vi.fn();
    renderTable({ documents: [sampleDocuments[0]], onInspect: inspect });
    openActions();
    expect(inspect).not.toHaveBeenCalled();
    const menu = screen.getByRole('menu');
    expect(menu.parentElement).toBe(document.body);
    const pdf = screen.getByRole('menuitem', { name: 'Open Data Structures SLM PDF' });
    expect(pdf.getAttribute('href')).toBe('/api/v1/documents/doc-1/file');
    expect(pdf.getAttribute('target')).toBe('_blank');
    expect(pdf.getAttribute('rel')).toBe('noopener noreferrer');
    fireEvent.keyDown(pdf, { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: 'Actions for Data Structures SLM' }),
    );
    openActions();
    fireEvent.click(screen.getByRole('menuitem', { name: 'View details' }));
    expect(inspect).toHaveBeenCalledOnce();
    expect(inspect).toHaveBeenCalledWith(sampleDocuments[0]);
  });

  it('does not inspect a module when clicking or pressing keys on its row', () => {
    const inspect = vi.fn();
    renderTable({ documents: [sampleDocuments[0]], onInspect: inspect });
    const title = screen.getByText('Data Structures SLM');
    const row = title.closest('tr')!;
    fireEvent.click(title);
    fireEvent.click(row);
    fireEvent.keyDown(row, { key: 'Enter' });
    fireEvent.keyDown(row, { key: ' ' });
    expect(inspect).not.toHaveBeenCalled();
    expect(row.hasAttribute('role')).toBe(false);
    expect(row.hasAttribute('tabindex')).toBe(false);
    expect(row.className).not.toContain('cursor-pointer');
  });

  it('opens the menu from the keyboard and inspects only the selected module', () => {
    const inspect = vi.fn();
    renderTable({ onInspect: inspect });
    const trigger = screen.getByRole('button', { name: 'Actions for Intro to IT Module' });
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const details = screen.getByRole('menuitem', { name: 'View details' });
    expect(document.activeElement).toBe(details);
    fireEvent.click(details);
    expect(inspect).toHaveBeenCalledOnce();
    expect(inspect).toHaveBeenCalledWith(sampleDocuments[1]);
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('keeps semantic headers and a matching action placeholder while loading', () => {
    const { container } = render(<DocumentTableSkeleton />);
    const headers = screen.getAllByRole('columnheader');
    expect(headers).toHaveLength(6);
    headers.forEach((header) => expect(header.getAttribute('scope')).toBe('col'));
    expect(container.querySelector('.size-10')).toBeTruthy();
  });
});
