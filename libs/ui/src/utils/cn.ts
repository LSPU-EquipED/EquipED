/**
 * Utility function to combine class names.
 * Simple implementation without external dependencies.
 */
export function cn(...classes: (string | undefined | null | boolean)[]): string {
  return classes
    .filter((cls) => typeof cls === 'string')
    .join(' ')
    .trim();
}
