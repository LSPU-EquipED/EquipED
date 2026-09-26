// @vitest-environment jsdom
import { renderHook, act } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { calculateNodeTops, useDiagramGeometry } from '../useDiagramGeometry';

describe('useDiagramGeometry', () => {
  it('calculates non-overlapping top positions for sources and consumers', () => {
    const visibleSourceIds = ['rubrics', 'syllabus', 'curriculum', 'policy'];
    const consumerIds = ['sme', 'coordinator', 'gad', 'itso', 'synthesis'];

    const { result } = renderHook(() =>
      useDiagramGeometry(visibleSourceIds, consumerIds, 496, 16),
    );

    const container = document.createElement('div');
    container.getBoundingClientRect = () => ({
      width: 800,
      height: 600,
      top: 100,
      left: 100,
      bottom: 700,
      right: 900,
      x: 100,
      y: 100,
      toJSON: () => {},
    });

    act(() => {
      result.current.registerContainer(container);
      result.current.updateGeometry();
    });

    // Preferred positions retain the original 496px desktop canvas layout.
    const { sourceTops, consumerTops, totalHeight } = result.current.layout;

    expect(Object.values(sourceTops)).toEqual([20, 144, 268, 392]);
    expect(Object.values(consumerTops)).toEqual([5, 104, 203, 303, 402]);

    expect(totalHeight).toBeGreaterThanOrEqual(496);
  });

  it('retains preferred slots unless measured cards would overlap', () => {
    const placement = calculateNodeTops(['a', 'b', 'c'], [20, 144, 268], { a: 140, b: 200, c: 72 }, 16);
    expect(placement.tops).toEqual({ a: 20, b: 176, c: 392 });
    expect(placement.totalHeight).toBe(464);
  });

  it('measures anchor points relative to container coordinates', () => {
    const visibleSourceIds = ['rubrics'];
    const consumerIds = ['sme'];

    const { result } = renderHook(() =>
      useDiagramGeometry(visibleSourceIds, consumerIds, 400, 16),
    );

    const container = document.createElement('div');
    container.getBoundingClientRect = () => ({
      width: 1000,
      height: 600,
      top: 50,
      left: 50,
      bottom: 650,
      right: 1050,
      x: 50,
      y: 50,
      toJSON: () => {},
    });

    const sourceEl = document.createElement('button');
    sourceEl.getBoundingClientRect = () => ({
      width: 400,
      height: 100,
      top: 70, // relative to viewport, so y in container is 70 - 50 = 20
      left: 50, // relative to viewport, so x in container is 50 - 50 = 0
      right: 450, // right edge relative to viewport, so anchor x is 450 - 50 = 400
      bottom: 170,
      x: 50,
      y: 70,
      toJSON: () => {},
    });

    const consumerEl = document.createElement('div');
    consumerEl.getBoundingClientRect = () => ({
      width: 400,
      height: 80,
      top: 80, // relative to viewport, so y in container is 80 - 50 = 30
      left: 600, // left edge relative to viewport, so anchor x is 600 - 50 = 550
      right: 1000,
      bottom: 160,
      x: 600,
      y: 80,
      toJSON: () => {},
    });

    act(() => {
      result.current.registerContainer(container);
      result.current.registerSource('rubrics')(sourceEl);
      result.current.registerConsumer('sme')(consumerEl);
      result.current.updateGeometry();
    });

    expect(result.current.anchors.sources.rubrics).toEqual({
      x: 400,
      y: 70, // (70 - 50) + 100/2 = 20 + 50 = 70
    });

    expect(result.current.anchors.consumers.sme).toEqual({
      x: 550, // 600 - 50 = 550
      y: 70, // (80 - 50) + 80/2 = 30 + 40 = 70
    });
  });
});
