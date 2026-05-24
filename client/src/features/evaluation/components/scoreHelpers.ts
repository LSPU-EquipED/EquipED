export function formatScore(value: number): string {
  const fixed = value.toFixed(2);
  return fixed.endsWith('.00') ? String(Math.round(value)) : fixed;
}

export function cleanJustification(text: string): string {
  if (!text) return text;
  return text
    .replace(/\bchunk_id\s+['"][^'"]+['"]/gi, '')
    .replace(/\bchunk_id\s+\S+/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}
