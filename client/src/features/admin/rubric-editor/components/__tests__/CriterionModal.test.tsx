// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { CriterionModal } from '../CriterionModal';

describe('CriterionModal', () => {
  afterEach(cleanup);

  it('renders add criterion form and submits valid data', () => {
    const onSave = vi.fn();
    const onClose = vi.fn();

    render(
      <CriterionModal
        isOpen={true}
        onClose={onClose}
        agentId="sme"
        domainTitle="Organization and Presentation"
        onSave={onSave}
        isPending={false}
      />,
    );

    expect(screen.getByRole('heading', { name: /add new criterion/i })).toBeDefined();

    fireEvent.change(screen.getByLabelText(/criterion id/i), {
      target: { value: 'OP-02' },
    });
    fireEvent.change(screen.getByLabelText(/^title/i), {
      target: { value: 'Learning Outcomes' },
    });
    fireEvent.change(screen.getByLabelText(/description \/ prompt entry/i), {
      target: { value: 'Learning outcomes are measurable and aligned.' },
    });
    fireEvent.change(screen.getByLabelText(/evaluation guidance/i), {
      target: { value: 'Score based on bloom taxonomy alignment.' },
    });

    fireEvent.click(screen.getByRole('button', { name: /add criterion/i }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        criterion_code: 'OP-02',
        title: 'Learning Outcomes',
        description: 'Learning outcomes are measurable and aligned.',
        strategy_config: expect.objectContaining({
          strategy: 'llm_rubric_guidance',
          guidance: 'Score based on bloom taxonomy alignment.',
        }),
      }),
    );
  });

  it('validates required fields before calling onSave', () => {
    const onSave = vi.fn();
    const onClose = vi.fn();

    render(
      <CriterionModal
        isOpen={true}
        onClose={onClose}
        agentId="sme"
        domainTitle="Organization"
        onSave={onSave}
        isPending={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /add criterion/i }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toBeDefined();
  });

  it('forces Coordinator A-05 to curriculum alignment', () => {
    const onSave = vi.fn();
    render(
      <CriterionModal
        isOpen={true}
        onClose={vi.fn()}
        agentId="coordinator"
        domainTitle="Assessment"
        onSave={onSave}
        isPending={false}
      />,
    );

    fireEvent.change(screen.getByLabelText(/criterion id/i), {
      target: { value: 'A-05' },
    });
    fireEvent.change(screen.getByLabelText(/^title/i), {
      target: { value: 'Curriculum Alignment' },
    });
    fireEvent.change(screen.getByLabelText(/description.*prompt entry/i), {
      target: { value: 'Evaluate objective alignment.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /add criterion/i }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        criterion_code: 'A-05',
        strategy_config: expect.objectContaining({
          strategy: 'curriculum_alignment',
        }),
      }),
    );
  });

  it('normalizes an existing invalid Coordinator A-05 strategy', () => {
    const onSave = vi.fn();
    render(
      <CriterionModal
        isOpen={true}
        onClose={vi.fn()}
        agentId="coordinator"
        domainTitle="Assessment"
        criterion={{
          rubric_criterion_id: 'criterion-a05',
          criterion_code: 'A-05',
          title: 'Curriculum Alignment',
          description: 'Evaluate objective alignment.',
          display_order: 0,
          strategy_config: {
            strategy: 'llm_rubric_guidance',
            guidance: 'Invalid historical configuration.',
          },
        }}
        onSave={onSave}
        isPending={false}
      />,
    );

    expect(screen.getByText('Curriculum Alignment')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        criterion_code: 'A-05',
        strategy_config: expect.objectContaining({ strategy: 'curriculum_alignment' }),
      }),
    );
  });
});
