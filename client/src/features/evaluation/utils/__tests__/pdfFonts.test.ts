// Unit tests for the optional Unicode font loader. The font loader is
// the seam where jsPDF gets either a Unicode-capable font or silently
// falls back to Helvetica; both branches must be covered because the
// OpenSpec says a missing asset must not abort the export.
//
// These tests use a small fake `addFileToVFS` / `addFont` so the
// helper is exercised without dragging jsPDF into the unit test
// graph. The actual jsPDF round-trip is covered by
// `scorecardPdf.smoke.test.ts`.
import { Buffer } from 'node:buffer';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  UNICODE_FONT_NAME,
  UNICODE_FONT_VFS_KEY,
  _resetFontRegistrationCache,
  arrayBufferToBase64,
  looksLikeTtf,
  registerOptionalUnicodeFont,
  safeFontWeight,
} from '../pdfFonts';

type FakePdf = {
  addFileToVFS: (name: string, data: string) => void;
  addFont: (file: string, name: string, weight: string) => void;
  calls: {
    vfs: Array<[string, string]>;
    font: Array<[string, string, string]>;
  };
};

function makePdf(): FakePdf {
  const calls = { vfs: [] as Array<[string, string]>, font: [] as Array<[string, string, string]> };
  return {
    calls,
    addFileToVFS: (name, data) => {
      calls.vfs.push([name, data]);
    },
    addFont: (file, name, weight) => {
      calls.font.push([file, name, weight]);
    },
  };
}

function ttfBuffer(): ArrayBuffer {
  // A minimal TTF-shaped buffer: 4-byte TTF magic, then padding. This
  // is just enough to satisfy `looksLikeTtf`.
  const bytes = new Uint8Array(16);
  bytes.set([0x00, 0x01, 0x00, 0x00]);
  return bytes.buffer;
}

function ttfResponse(buffer: ArrayBuffer, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    arrayBuffer: async () => buffer,
  } as unknown as Response;
}

describe('looksLikeTtf', () => {
  it('accepts buffers that start with the TTF magic header', () => {
    expect(looksLikeTtf(ttfBuffer())).toBe(true);
  });

  it('rejects empty or short buffers', () => {
    expect(looksLikeTtf(new ArrayBuffer(0))).toBe(false);
    expect(looksLikeTtf(new ArrayBuffer(2))).toBe(false);
  });

  it('rejects OpenType CFF magic and other fonts', () => {
    const otf = new Uint8Array([0x4f, 0x54, 0x54, 0x4f]);
    expect(looksLikeTtf(otf.buffer)).toBe(false);
    const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47]);
    expect(looksLikeTtf(png.buffer)).toBe(false);
  });
});

describe('arrayBufferToBase64', () => {
  it('round-trips arbitrary bytes', () => {
    const bytes = new Uint8Array([0, 1, 2, 254, 255, 128, 64]);
    const b64 = arrayBufferToBase64(bytes.buffer);
    const decoded = Buffer.from(b64, 'base64');
    expect(Array.from(decoded)).toEqual(Array.from(bytes));
  });

  it('handles empty buffers', () => {
    expect(arrayBufferToBase64(new ArrayBuffer(0))).toBe('');
  });
});

describe('registerOptionalUnicodeFont', () => {
  beforeEach(() => {
    _resetFontRegistrationCache();
  });

  it('registers the Unicode font when the asset fetches successfully', async () => {
    const pdf = makePdf();
    const fetcher = (async () => ttfResponse(ttfBuffer())) as unknown as typeof fetch;

    const result = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });

    expect(result.registered).toBe(true);
    expect(result.fontName).toBe(UNICODE_FONT_NAME);
    expect(result.sizeBytes).toBe(16);
    expect(result.fontUrl).toBe('/fonts/NotoSans-Regular.ttf');
    expect(pdf.calls.vfs).toHaveLength(1);
    expect(pdf.calls.vfs[0][0]).toBe(UNICODE_FONT_VFS_KEY);
    expect(pdf.calls.font).toEqual([
      [UNICODE_FONT_VFS_KEY, UNICODE_FONT_NAME, 'normal'],
    ]);
  });

  it('falls back to Helvetica when the asset returns a non-OK status', async () => {
    const pdf = makePdf();
    const fetcher = (async () => ttfResponse(new ArrayBuffer(0), 404)) as unknown as typeof fetch;

    const result = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });

    expect(result.registered).toBe(false);
    expect(result.fontName).toBe('helvetica');
    expect(result.diagnostic).toContain('not found');
    expect(pdf.calls.vfs).toHaveLength(0);
    expect(pdf.calls.font).toHaveLength(0);
  });

  it('falls back to Helvetica when the asset is not a valid TTF', async () => {
    const pdf = makePdf();
    const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]).buffer;
    const fetcher = (async () => ttfResponse(png)) as unknown as typeof fetch;

    const result = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });

    expect(result.registered).toBe(false);
    expect(result.fontName).toBe('helvetica');
    expect(result.diagnostic).toContain('not a valid TrueType');
    expect(pdf.calls.vfs).toHaveLength(0);
  });

  it('refuses to register an asset that is suspiciously large', async () => {
    const pdf = makePdf();
    // 5 MB buffer that still starts with the TTF magic. The loader
    // should refuse and fall back rather than try to base64-encode it.
    const big = new Uint8Array(5 * 1024 * 1024);
    big.set([0x00, 0x01, 0x00, 0x00]);
    const fetcher = (async () => ttfResponse(big.buffer)) as unknown as typeof fetch;

    const result = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });

    expect(result.registered).toBe(false);
    expect(result.fontName).toBe('helvetica');
    expect(result.diagnostic).toContain('unexpectedly large');
  });

  it('falls back to Helvetica when fetch throws (e.g. network error)', async () => {
    const pdf = makePdf();
    const fetcher = (async () => {
      throw new Error('offline');
    }) as unknown as typeof fetch;

    const result = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });

    expect(result.registered).toBe(false);
    expect(result.fontName).toBe('helvetica');
    expect(result.diagnostic).toContain('offline');
  });

  it('reuses the cached payload without re-fetching on the same document', async () => {
    const pdf = makePdf();
    let fetchCount = 0;
    const fetcher = (async () => {
      fetchCount += 1;
      return ttfResponse(ttfBuffer());
    }) as unknown as typeof fetch;

    const first = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });
    const second = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });

    // The asset was only downloaded once.
    expect(fetchCount).toBe(1);
    // The second call did not re-register the font on the same
    // document (it would have been a no-op but the loader should
    // recognise the document already has the font).
    expect(pdf.calls.vfs).toHaveLength(1);
    expect(pdf.calls.font).toHaveLength(1);
    expect(second.fromCache).toBe(true);
    expect(second.registered).toBe(true);
    // The first call's result is the fresh registration; the second
    // is the cache hit. They are equivalent but distinct objects.
    expect(first.registered).toBe(true);
    expect(second.fontName).toBe(first.fontName);
  });

  it('re-registers when the URL changes', async () => {
    const pdf = makePdf();
    let fetchCount = 0;
    const fetcher = (async (input: RequestInfo | URL) => {
      fetchCount += 1;
      // The fetcher decides success vs 404 by inspecting the URL.
      if (String(input).endsWith('missing.ttf')) {
        return ttfResponse(new ArrayBuffer(0), 404);
      }
      return ttfResponse(ttfBuffer());
    }) as unknown as typeof fetch;

    const first = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fontUrl: '/fonts/missing.ttf',
      fetcher,
    });
    const second = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fontUrl: '/fonts/NotoSans-Regular.ttf',
      fetcher,
    });

    expect(fetchCount).toBe(2);
    expect(first.registered).toBe(false);
    expect(second.registered).toBe(true);
  });
});

// Regression: the per-document registration must run for *every* new
// jsPDF document. If the helper caches a previous document's
// addFont call, a fresh `new jsPDF()` will be left in an "unknown
// font" state and any text drawn with the Unicode name will throw at
// save time. This test guards that contract end-to-end across two
// distinct fake documents without resetting the cache.
describe('registerOptionalUnicodeFont - per-document registration', () => {
  it('registers the cached font on a second jsPDF document without re-fetching', async () => {
    _resetFontRegistrationCache();
    let fetchCount = 0;
    const fetcher = (async () => {
      fetchCount += 1;
      return ttfResponse(ttfBuffer());
    }) as unknown as typeof fetch;

    const pdf1 = makePdf();
    const pdf2 = makePdf();

    const first = await registerOptionalUnicodeFont(pdf1 as never, {
      baseUrl: '/',
      fetcher,
    });
    expect(first.registered).toBe(true);
    expect(first.fromCache).toBeUndefined();
    expect(pdf1.calls.vfs).toHaveLength(1);
    expect(pdf1.calls.font).toHaveLength(1);

    // Crucially: we do NOT call _resetFontRegistrationCache() between
    // the two exports. The download is reused, but pdf2 must still
    // receive its own addFileToVFS / addFont call.
    const second = await registerOptionalUnicodeFont(pdf2 as never, {
      baseUrl: '/',
      fetcher,
    });
    expect(second.registered).toBe(true);
    expect(second.fontName).toBe(UNICODE_FONT_NAME);
    expect(fetchCount).toBe(1);
    // The cache was hit for the payload, not for the registration.
    expect(second.fromCache).toBeUndefined();

    expect(pdf2.calls.vfs).toHaveLength(1);
    expect(pdf2.calls.vfs[0][0]).toBe(UNICODE_FONT_VFS_KEY);
    expect(pdf2.calls.font).toEqual([
      [UNICODE_FONT_VFS_KEY, UNICODE_FONT_NAME, 'normal'],
    ]);

    // The base64 payload should be identical to the one pdf1 received.
    expect(pdf2.calls.vfs[0][1]).toBe(pdf1.calls.vfs[0][1]);
  });

  it('registers on three successive documents without skipping any', async () => {
    _resetFontRegistrationCache();
    const fetcher = (async () => ttfResponse(ttfBuffer())) as unknown as typeof fetch;

    const docs = [makePdf(), makePdf(), makePdf()];
    for (const pdf of docs) {
      const result = await registerOptionalUnicodeFont(pdf as never, {
        baseUrl: '/',
        fetcher,
      });
      expect(result.registered).toBe(true);
      expect(result.fontName).toBe(UNICODE_FONT_NAME);
      expect(pdf.calls.vfs).toHaveLength(1);
      expect(pdf.calls.font).toEqual([
        [UNICODE_FONT_VFS_KEY, UNICODE_FONT_NAME, 'normal'],
      ]);
    }
  });
});

describe('safeFontWeight', () => {
  it('downgrades bold to normal under NotoSans', () => {
    expect(safeFontWeight(UNICODE_FONT_NAME, 'bold')).toBe('normal');
    expect(safeFontWeight(UNICODE_FONT_NAME, 'bolditalic')).toBe('normal');
    expect(safeFontWeight(UNICODE_FONT_NAME, 'normal')).toBe('normal');
    expect(safeFontWeight(UNICODE_FONT_NAME, 'italic')).toBe('normal');
  });

  it('preserves bold under Helvetica', () => {
    expect(safeFontWeight('helvetica', 'bold')).toBe('bold');
    expect(safeFontWeight('helvetica', 'bolditalic')).toBe('bold');
    expect(safeFontWeight('helvetica', 'normal')).toBe('normal');
  });
});

describe('registerOptionalUnicodeFont with the real bundled font', () => {
  // The test harness only runs this block when the asset is present on
  // disk so a fresh checkout without the font still passes the suite.
  it('loads and registers client/public/fonts/NotoSans-Regular.ttf', async () => {
    _resetFontRegistrationCache();
    const fontPath = resolve(
      __dirname,
      '..',
      '..',
      '..',
      '..',
      '..',
      'public',
      'fonts',
      'NotoSans-Regular.ttf',
    );
    const buffer = await readFile(fontPath).catch(() => null);
    if (!buffer) {
      // Skip silently when the font has not been committed yet.
      return;
    }

    const ab = buffer.buffer.slice(
      buffer.byteOffset,
      buffer.byteOffset + buffer.byteLength,
    );
    expect(looksLikeTtf(ab)).toBe(true);

    const pdf = makePdf();
    const fetcher = (async () => ttfResponse(ab)) as unknown as typeof fetch;
    const result = await registerOptionalUnicodeFont(pdf as never, {
      baseUrl: '/',
      fetcher,
    });

    expect(result.registered).toBe(true);
    expect(result.fontName).toBe(UNICODE_FONT_NAME);
    expect(result.sizeBytes).toBeGreaterThan(100_000);
    // The Noto Sans Regular TTF committed in the repo is ~ 430 KB. If
    // a future build of the asset changes the size, update the bound.
    expect(result.sizeBytes).toBeLessThan(700_000);
    expect(pdf.calls.vfs).toHaveLength(1);
    expect(pdf.calls.vfs[0][0]).toBe(UNICODE_FONT_VFS_KEY);
  });
});
