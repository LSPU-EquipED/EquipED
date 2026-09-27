import { useCallback, useEffect, useRef, useState } from 'react';

export type Point = {
  x: number;
  y: number;
};

export type NodeAnchorPoints = {
  sources: Record<string, Point>;
  consumers: Record<string, Point>;
};

export type NodeLayoutInfo = {
  sourceTops: Record<string, number>;
  consumerTops: Record<string, number>;
  totalHeight: number;
};

function equalPositions(previous: Record<string, number>, next: Record<string, number>) {
  const ids = Object.keys(next);
  return Object.keys(previous).length === ids.length &&
    ids.every((id) => previous[id] === next[id]);
}

function equalAnchors(previous: Record<string, Point>, next: Record<string, Point>) {
  const ids = Object.keys(next);
  return Object.keys(previous).length === ids.length &&
    ids.every((id) => previous[id]?.x === next[id].x && previous[id]?.y === next[id].y);
}

function useNodeRefs() {
  const elements = useRef<Record<string, HTMLElement | null>>({});
  const callbacks = useRef(new Map<string, (element: HTMLElement | null) => void>());
  const register = useCallback((id: string) => {
    let callback = callbacks.current.get(id);
    if (!callback) {
      callback = (element) => {
        elements.current[id] = element;
      };
      callbacks.current.set(id, callback);
    }
    return callback;
  }, []);
  return { elements, register };
}

export function calculateNodeTops(
  ids: string[],
  preferredTops: number[],
  heights: Record<string, number>,
  verticalGap: number,
) {
  const tops: Record<string, number> = {};
  let previousBottom = 0;
  ids.forEach((id, index) => {
    const preferred = preferredTops[index] ?? previousBottom + verticalGap;
    tops[id] = index === 0 ? preferred : Math.max(preferred, previousBottom + verticalGap);
    previousBottom = tops[id] + (heights[id] ?? 0);
  });
  return { tops, totalHeight: ids.length ? previousBottom : 0 };
}

export function useDiagramGeometry(
  visibleSourceIds: string[],
  consumerIds: string[],
  minDiagramHeight = 496,
  verticalGap = 16,
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { elements: sourceRefs, register: registerSource } = useNodeRefs();
  const { elements: consumerRefs, register: registerConsumer } = useNodeRefs();

  const registerContainer = useCallback((el: HTMLDivElement | null) => {
    containerRef.current = el;
  }, []);

  const [anchors, setAnchors] = useState<NodeAnchorPoints>({
    sources: {},
    consumers: {},
  });

  const [layout, setLayout] = useState<NodeLayoutInfo>({
    sourceTops: {},
    consumerTops: {},
    totalHeight: minDiagramHeight,
  });

  const updateGeometry = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const containerRect = container.getBoundingClientRect();

    // Preserve the original canvas slots unless measured card heights require a push.
    const sourceHeights: Record<string, number> = {};
    const sourceRects: Record<string, DOMRect> = {};
    for (const id of visibleSourceIds) {
      const el = sourceRefs.current[id];
      if (el) sourceRects[id] = el.getBoundingClientRect();
      sourceHeights[id] = el ? el.offsetHeight || sourceRects[id].height || 88 : 88;
    }
    const consumerHeights: Record<string, number> = {};
    const consumerRects: Record<string, DOMRect> = {};
    for (const id of consumerIds) {
      const el = consumerRefs.current[id];
      if (el) consumerRects[id] = el.getBoundingClientRect();
      consumerHeights[id] = el ? el.offsetHeight || consumerRects[id].height || 72 : 72;
    }
    const sourcePlacement = calculateNodeTops(visibleSourceIds, [20, 144, 268, 392], sourceHeights, verticalGap);
    const consumerPlacement = calculateNodeTops(consumerIds, [5, 104, 203, 303, 402], consumerHeights, verticalGap);
    const computedSourceTops = sourcePlacement.tops;
    const computedConsumerTops = consumerPlacement.tops;
    const calculatedHeight = Math.max(minDiagramHeight, sourcePlacement.totalHeight, consumerPlacement.totalHeight);

    // Reuse the same measurements for connector endpoints.
    const newSourceAnchors: Record<string, Point> = {};
    for (const id of visibleSourceIds) {
      const rect = sourceRects[id];
      if (rect) {
        newSourceAnchors[id] = {
          x: rect.right - containerRect.left,
          y: rect.top - containerRect.top + rect.height / 2,
        };
      } else {
        const top = computedSourceTops[id] ?? 0;
        newSourceAnchors[id] = {
          x: containerRect.width * 0.43,
          y: top + 44,
        };
      }
    }

    const newConsumerAnchors: Record<string, Point> = {};
    for (const id of consumerIds) {
      const rect = consumerRects[id];
      if (rect) {
        newConsumerAnchors[id] = {
          x: rect.left - containerRect.left,
          y: rect.top - containerRect.top + rect.height / 2,
        };
      } else {
        const top = computedConsumerTops[id] ?? 0;
        newConsumerAnchors[id] = {
          x: containerRect.width * 0.57,
          y: top + 36,
        };
      }
    }

    const nextLayout = {
      sourceTops: computedSourceTops,
      consumerTops: computedConsumerTops,
      totalHeight: calculatedHeight,
    };
    setLayout((previous) =>
      previous.totalHeight === calculatedHeight &&
      equalPositions(previous.sourceTops, computedSourceTops) &&
      equalPositions(previous.consumerTops, computedConsumerTops)
        ? previous
        : nextLayout,
    );

    const nextAnchors = {
      sources: newSourceAnchors,
      consumers: newConsumerAnchors,
    };
    setAnchors((previous) =>
      equalAnchors(previous.sources, newSourceAnchors) &&
      equalAnchors(previous.consumers, newConsumerAnchors)
        ? previous
        : nextAnchors,
    );
  }, [visibleSourceIds, consumerIds, minDiagramHeight, verticalGap, sourceRefs, consumerRefs]);

  // Update geometry on mount, layout changes, or source/consumer changes
  useEffect(() => {
    updateGeometry();
  }, [updateGeometry]);

  // Set up resize observer / window resize
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateGeometry);
      return () => {
        window.removeEventListener('resize', updateGeometry);
      };
    }

    const observer = new ResizeObserver(() => {
      updateGeometry();
    });

    observer.observe(container);

    for (const id of visibleSourceIds) {
      const el = sourceRefs.current[id];
      if (el) observer.observe(el);
    }
    for (const id of consumerIds) {
      const el = consumerRefs.current[id];
      if (el) observer.observe(el);
    }

    return () => {
      observer.disconnect();
    };
  }, [visibleSourceIds, consumerIds, updateGeometry, sourceRefs, consumerRefs]);

  return {
    registerContainer,
    registerSource,
    registerConsumer,
    anchors,
    layout,
    updateGeometry,
  };
}
