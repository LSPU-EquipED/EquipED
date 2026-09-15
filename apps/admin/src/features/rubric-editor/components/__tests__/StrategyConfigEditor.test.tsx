// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { StrategyConfigEditor } from '../StrategyConfigEditor';
import type {
  CountBandConfig,
  CurriculumAlignmentConfig,
  LlmRubricGuidanceConfig,
  RatioBandConfig,
} from '../../types';

describe('StrategyConfigEditor', () => {
  afterEach(cleanup);

  it('renders LLM rubric guidance editor with guidance textarea', () => {
    const onChange = vi.fn();
    const config: LlmRubricGuidanceConfig = {
      strategy: 'llm_rubric_guidance',
      guidance: 'Evaluate topic flow and sectioning.',
      level_descriptors: null,
    };

    render(<StrategyConfigEditor agentId="sme" value={config} onChange={onChange} />);

    const textarea = screen.getByLabelText(/evaluation guidance/i) as HTMLTextAreaElement;
    expect(textarea.value).toBe('Evaluate topic flow and sectioning.');

    fireEvent.change(textarea, { target: { value: 'Updated guidance' } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        strategy: 'llm_rubric_guidance',
        guidance: 'Updated guidance',
      }),
    );
  });

  it('toggles level descriptors for LLM guidance', () => {
    const onChange = vi.fn();
    const config: LlmRubricGuidanceConfig = {
      strategy: 'llm_rubric_guidance',
      guidance: 'Evaluate topic flow.',
      level_descriptors: null,
    };

    render(<StrategyConfigEditor agentId="itso" value={config} onChange={onChange} />);

    const checkbox = screen.getByRole('checkbox', {
      name: /include exact 1–4 score level descriptors/i,
    });
    expect((checkbox as HTMLInputElement).checked).toBe(false);

    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        level_descriptors: expect.arrayContaining([
          expect.objectContaining({ score: 4 }),
          expect.objectContaining({ score: 3 }),
          expect.objectContaining({ score: 2 }),
          expect.objectContaining({ score: 1 }),
        ]),
      }),
    );
  });

  it('renders count band editor with mode and thresholds', () => {
    const onChange = vi.fn();
    const config: CountBandConfig = {
      strategy: 'count_band',
      mode: 'maximum_count',
      threshold_4: 0,
      threshold_3: 1,
      threshold_2: 3,
    };

    render(<StrategyConfigEditor agentId="gad" value={config} onChange={onChange} />);

    expect(screen.getByLabelText(/score 4 threshold/i)).toBeDefined();
    expect(screen.getByLabelText(/score 3 threshold/i)).toBeDefined();
    expect(screen.getByLabelText(/score 2 threshold/i)).toBeDefined();

    fireEvent.change(screen.getByLabelText(/score 4 threshold/i), {
      target: { value: '2' },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        strategy: 'count_band',
        threshold_4: 2,
      }),
    );
  });

  it('renders ratio band editor with short-sample toggle in coverage mode', () => {
    const onChange = vi.fn();
    const config: RatioBandConfig = {
      strategy: 'ratio_band',
      mode: 'coverage_percentage',
      threshold_4: 90.0,
      threshold_3: 75.0,
      threshold_2: 60.0,
      short_sample: null,
    };

    render(<StrategyConfigEditor agentId="sme" value={config} onChange={onChange} />);

    const toggle = screen.getByRole('checkbox', {
      name: /enable short-sample override/i,
    });
    expect(toggle).toBeDefined();

    fireEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        short_sample: expect.objectContaining({
          min_units: 3,
          max_issues_4: 0,
          max_issues_3: 1,
          max_issues_2: 2,
        }),
      }),
    );
  });

  it('renders curriculum alignment guidance editor for Coordinator', () => {
    const onChange = vi.fn();
    const config: CurriculumAlignmentConfig = {
      strategy: 'curriculum_alignment',
      guidance: 'Compare module ILOs with syllabus items.',
    };

    render(<StrategyConfigEditor agentId="coordinator" value={config} onChange={onChange} />);

    const textarea = screen.getByLabelText(/curriculum alignment guidance/i) as HTMLTextAreaElement;
    expect(textarea.value).toBe('Compare module ILOs with syllabus items.');
  });
});
