// Optional Unicode-capable font registration for jsPDF.
//
// jsPDF's built-in Helvetica / Times / Courier fonts only cover WinAnsi
// (Latin-1). Institutional content frequently uses Filipino / Tagalog
// names and characters outside that range, so the export looks for a
// pre-bundled Unicode TTF in `public/fonts/`. If the file is missing
// (e.g. because no font has been added yet, or the asset unexpectedly
// fails to load), the helpers fall back to the built-in font so the
// export never aborts.
//
// The expected path is `${BASE_URL}fonts/NotoSans-Regular.ttf`. The
// asset is fetched lazily on the first export, so users who never
// export a PDF pay zero bundle cost. The fetch is a same-origin
// request to the static-asset server (Vite dev server in development,
// the bundled output in production) — it does not make any external
// network call.
//
// Caching model: the downloaded/decoded base64 payload is keyed by
// `fontUrl` and reused across calls. The actual `pdf.addFileToVFS` /
// `pdf.addFont` registration MUST run on every call, because each
// `new jsPDF()` instance owns its own VFS — caching the registration
// result from a previous document would skip registration on the new
// document and silently leave jsPDF in an "unknown font" state.
//
// The shape of this module is intentionally narrow: it exports a
// `registerOptionalUnicodeFont` helper plus a font name constant. The
// PDF generators call it once before drawing text and then reference
// `UNICODE_FONT_NAME` everywhere instead of hard-coding 'helvetica'.

import type { jsPDF as JsPdfDocument } from 'jspdf';

export const UNICODE_FONT_NAME = 'NotoSans';
export const UNICODE_FONT_VFS_KEY = `${UNICODE_FONT_NAME}-Regular.ttf`;

// Default font path. The path is intentionally not imported from
// `import.meta.env` at module top level so the helper is testable in a
// Node-like environment.
const DEFAULT_FONT_RELATIVE_PATH = 'fonts/NotoSans-Regular.ttf';

// The TrueType Font magic header. Bytes 0x00 0x01 0x00 0x00 identify a
// TTF; OpenType CFF (`.otf` with OTF flavor) starts with 0x4F 0x54 0x54
// 0x4F. We only ship TTF today, so the check is intentionally narrow —
// extending to OTF would mean registering a different VFS key.
const TTF_MAGIC = [0x00, 0x01, 0x00, 0x00] as const;

// Soft upper bound for the asset we expect. Noto Sans Regular TTF is
// ~ 300 KB. Anything dramatically larger is almost certainly the wrong
// file, so we refuse to register it instead of crashing the export
// with an out-of-memory `String.fromCharCode`.
const MAX_FONT_BYTES = 4 * 1024 * 1024; // 4 MB

export interface FontRegistrationResult {
  /** The font name to pass to `pdf.setFont(...)`. */
  fontName: string;
  /** True iff the Unicode TTF was successfully registered. */
  registered: boolean;
  /**
   * Reason text, suitable for surfacing in a non-blocking diagnostic
   * log when an export runs without a Unicode font.
   */
  diagnostic: string;
  /** The URL the asset was fetched from (or the URL that was attempted). */
  fontUrl: string;
  /** Size of the asset in bytes when registration succeeded. */
  sizeBytes?: number;
  /** True when the data was served from the in-process cache. */
  fromCache?: boolean;
}

// Cache the decoded font payload (base64) and the URL it came from.
// The `pdf` instance is intentionally NOT cached — each `new jsPDF()`
// owns its own VFS and must receive its own addFileToVFS / addFont
// call.
let cachedFontBase64: string | null = null;
let cachedFontUrl: string | null = null;
let cachedFontSize: number | null = null;

// Track per-document registration so we never double-register the
// same font on the same document (which jsPDF tolerates but is still
// wasted work, and which would mask the regression we are guarding
// against here).
const registeredPdfs = new WeakSet<JsPdfDocument>();

export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  // Chunk the conversion to avoid `String.fromCharCode.apply` arg limits
  // on large font payloads (Noto Sans Regular TTF is ~ 300 KB).
  const bytes = new Uint8Array(buffer);
  if (bytes.length === 0) return '';
  const chunkSize = 0x8000;
  let binary = '';
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

// jsPDF's `setFont(name, style)` accepts a weight the font may not
// have been registered with. When the bundled Unicode TTF is loaded
// it is the regular-weight Noto Sans only, so requesting 'bold' would
// either throw at save time or fall back to a synthetic bold that
// some PDF readers render as missing glyphs.
//
// `safeFontWeight` is the single seam through which the export passes
// font weights. Under NotoSans, every "bold" request is downgraded
// to 'normal' and the caller is expected to provide visual
// hierarchy through other channels (size, color, capitalization,
// fillColor on table headers).
export type FontWeight = 'normal' | 'bold' | 'italic' | 'bolditalic';

export function safeFontWeight(
  fontName: string,
  requested: FontWeight,
): 'normal' | 'bold' {
  if (fontName === UNICODE_FONT_NAME) {
    // The Unicode TTF is registered as 'normal' only. Italic
    // requests are also downgraded to 'normal' for the same reason.
    return 'normal';
  }
  // Built-in Helvetica has bold. We don't need to model italic here
  // because the export never asks for it.
  if (requested === 'bold' || requested === 'bolditalic') return 'bold';
  return 'normal';
}

export function looksLikeTtf(buffer: ArrayBuffer): boolean {
  if (!buffer || buffer.byteLength < TTF_MAGIC.length) return false;
  const head = new Uint8Array(buffer, 0, TTF_MAGIC.length);
  for (let i = 0; i < TTF_MAGIC.length; i += 1) {
    if (head[i] !== TTF_MAGIC[i]) return false;
  }
  return true;
}

function resolveFontUrl(options: { baseUrl?: string; fontUrl?: string }): string {
  if (options.fontUrl) return options.fontUrl;
  const base = options.baseUrl ?? (import.meta.env?.BASE_URL as string | undefined) ?? '/';
  return `${base.replace(/\/?$/, '/')}${DEFAULT_FONT_RELATIVE_PATH}`;
}

function registerOnDocument(
  pdf: JsPdfDocument,
  base64: string,
): FontRegistrationResult {
  pdf.addFileToVFS(UNICODE_FONT_VFS_KEY, base64);
  pdf.addFont(UNICODE_FONT_VFS_KEY, UNICODE_FONT_NAME, 'normal');
  registeredPdfs.add(pdf);
  return {
    fontName: UNICODE_FONT_NAME,
    registered: true,
    fontUrl: cachedFontUrl ?? '',
    sizeBytes: cachedFontSize ?? undefined,
    diagnostic: `Registered ${UNICODE_FONT_NAME} on document from ${cachedFontUrl ?? 'cache'}.`,
  };
}

export async function registerOptionalUnicodeFont(
  pdf: JsPdfDocument,
  options: { baseUrl?: string; fontUrl?: string; fetcher?: typeof fetch } = {},
): Promise<FontRegistrationResult> {
  const fontUrl = resolveFontUrl(options);
  const fetcher = options.fetcher ?? (typeof fetch === 'function' ? fetch.bind(globalThis) : null);

  // Same document, same URL, and the asset is already cached locally:
  // registration is already done for this `pdf`; just return the
  // existing result without calling fetch or addFont again.
  if (
    cachedFontBase64 !== null &&
    cachedFontUrl === fontUrl &&
    registeredPdfs.has(pdf)
  ) {
    return {
      fontName: UNICODE_FONT_NAME,
      registered: true,
      fontUrl,
      sizeBytes: cachedFontSize ?? undefined,
      fromCache: true,
      diagnostic: `Reusing cached ${UNICODE_FONT_NAME} for current document.`,
    };
  }

  // Cache hit across documents: a NEW jsPDF document was created
  // since the last export. We must re-run addFileToVFS / addFont on
  // this new document, but the heavy work (fetch + base64 encode) is
  // already done.
  if (cachedFontBase64 !== null && cachedFontUrl === fontUrl && !registeredPdfs.has(pdf)) {
    return registerOnDocument(pdf, cachedFontBase64);
  }

  if (!fetcher) {
    return {
      fontName: 'helvetica',
      registered: false,
      fontUrl,
      diagnostic: 'fetch is unavailable; using built-in Helvetica.',
    };
  }

  try {
    const response = await fetcher(fontUrl);
    if (!response.ok) {
      return {
        fontName: 'helvetica',
        registered: false,
        fontUrl,
        diagnostic: `Unicode font asset not found at ${fontUrl} (status ${response.status}); using built-in Helvetica.`,
      };
    }
    const buffer = await response.arrayBuffer();
    if (!looksLikeTtf(buffer)) {
      return {
        fontName: 'helvetica',
        registered: false,
        fontUrl,
        diagnostic: `Asset at ${fontUrl} is not a valid TrueType font; using built-in Helvetica.`,
      };
    }
    if (buffer.byteLength > MAX_FONT_BYTES) {
      return {
        fontName: 'helvetica',
        registered: false,
        fontUrl,
        diagnostic: `Asset at ${fontUrl} is unexpectedly large (${buffer.byteLength} bytes); using built-in Helvetica.`,
      };
    }
    const base64 = arrayBufferToBase64(buffer);
    cachedFontBase64 = base64;
    cachedFontUrl = fontUrl;
    cachedFontSize = buffer.byteLength;
    return registerOnDocument(pdf, base64);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      fontName: 'helvetica',
      registered: false,
      fontUrl,
      diagnostic: `Unicode font could not be loaded from ${fontUrl} (${message}); using built-in Helvetica.`,
    };
  }
}

// Reset the cache. Useful in tests so a different font path or missing
// file can be exercised between runs.
export function _resetFontRegistrationCache(): void {
  cachedFontBase64 = null;
  cachedFontUrl = null;
  cachedFontSize = null;
  // WeakSet entries are GC'd with their keys; resetting the
  // module-level handle drops the set entirely.
}
