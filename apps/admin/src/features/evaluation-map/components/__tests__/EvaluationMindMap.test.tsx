// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { EvaluationMindMap } from '../EvaluationMindMap';

describe('EvaluationMindMap', () => {
  afterEach(cleanup);

  it('renders workstation header and lineage blueprint title', () => {
    render(<EvaluationMindMap />);

    expect(screen.getByText('Institutional Architecture Blueprint')).toBeDefined();
    expect(
      screen.getByText('Multi-Agent Knowledge Lineage & Data Residency Map'),
    ).toBeDefined();
    expect(screen.getByText(/Advisory Governance/i)).toBeDefined();
  });

  it('renders quick preset buttons and updates inspector on preset selection', () => {
    render(<EvaluationMindMap />);

    const matrixPresetBtn = screen.getByRole('button', { name: 'Monitoring Matrix' });
    expect(matrixPresetBtn).toBeDefined();

    fireEvent.click(matrixPresetBtn);

    expect(screen.getByText(/Lineage Inspector: Monitoring matrix/i)).toBeDefined();
  });

  it('renders the 3-column canvas and lineage inspector details', () => {
    render(<EvaluationMindMap />);

    expect(screen.getByText('References & Ingestion')).toBeDefined();
    expect(screen.getByText('Specialist Processes')).toBeDefined();
    expect(screen.getByText('Accredited Outputs')).toBeDefined();
    expect(screen.getByText(/Ingestion Inputs Consumed/i)).toBeDefined();
    expect(screen.getByText(/Specialist Processes Executed/i)).toBeDefined();
    expect(screen.getByText(/SLMs are direct evaluation input/i)).toBeDefined();
  });
});
