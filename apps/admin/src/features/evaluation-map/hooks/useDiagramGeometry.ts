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
  const sourceRefs = useRef<Record<string, HTMLElement | null>>({});
  const consumerRefs = useRef<Record<string, HTMLElement | null>>({});

  const registerContainer = useCallback((el: HTMLDivElement | null) => {
    containerRef.current = el;
  }, []);

  const registerSource = useCallback((id: string) => {
    return (el: HTMLElement | null) => {
      sourceRefs.current[id] = el;
    };
  }, []);

  const registerConsumer = useCallback((id: string) => {
    return (el: HTMLElement | null) => {
      consumerRefs.current[id] = el;
    };
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
    for (const id of visibleSourceIds) {
      const el = sourceRefs.current[id];
      sourceHeights[id] = el ? el.offsetHeight || el.getBoundingClientRect().height || 88 : 88;
    }
    const consumerHeights: Record<string, number> = {};
    for (const id of consumerIds) {
      const el = consumerRefs.current[id];
      consumerHeights[id] = el ? el.offsetHeight || el.getBoundingClientRect().height || 72 : 72;
    }
    const sourcePlacement = calculateNodeTops(visibleSourceIds, [20, 144, 268, 392], sourceHeights, verticalGap);
    const consumerPlacement = calculateNodeTops(consumerIds, [5, 104, 203, 303, 402], consumerHeights, verticalGap);
    const computedSourceTops = sourcePlacement.tops;
    const computedConsumerTops = consumerPlacement.tops;
    const calculatedHeight = Math.max(minDiagramHeight, sourcePlacement.totalHeight, consumerPlacement.totalHeight);

    // 2. Compute anchor points relative to container
    const newSourceAnchors: Record<string, Point> = {};
    for (const id of visibleSourceIds) {
      const el = sourceRefs.current[id];
      if (el) {
        const rect = el.getBoundingClientRect();
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
      const el = consumerRefs.current[id];
      if (el) {
        const rect = el.getBoundingClientRect();
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

    setLayout({
      sourceTops: computedSourceTops,
      consumerTops: computedConsumerTops,
      totalHeight: calculatedHeight,
    });

    setAnchors({
      sources: newSourceAnchors,
      consumers: newConsumerAnchors,
    });
  }, [visibleSourceIds, consumerIds, minDiagramHeight, verticalGap]);

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
  }, [visibleSourceIds, consumerIds, updateGeometry]);

  return {
    registerContainer,
    registerSource,
    registerConsumer,
    anchors,
    layout,
    updateGeometry,
  };
}
