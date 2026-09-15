// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { lspuLogoUrl } from '../index';

describe('Assets export', () => {
  it('exports a valid lspuLogoUrl string', () => {
    expect(lspuLogoUrl).toBeDefined();
    expect(typeof lspuLogoUrl).toBe('string');
    expect(lspuLogoUrl.length).toBeGreaterThan(0);
  });
});
