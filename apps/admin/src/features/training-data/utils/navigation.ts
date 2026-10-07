/** Small seam so tests can spy on browser navigation. */
export function navigateTo(url: string): void {
  window.location.href = url;
}
