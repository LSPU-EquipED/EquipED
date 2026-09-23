import { describe, expect, it } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

describe('monitoring-matrix feature boundaries', () => {
  it('monitoring-matrix feature never imports from evaluation feature (strict feature boundary)', () => {
    const matrixDir = path.resolve(__dirname, '..');
    expect(path.basename(matrixDir)).toBe('monitoring-matrix');
    const files: string[] = [];
    function scanDir(dir: string) {
      for (const entry of fs.readdirSync(dir)) {
        const full = path.join(dir, entry);
        if (fs.statSync(full).isDirectory()) {
          if (entry !== '__tests__') scanDir(full);
        } else if (/\.(ts|tsx)$/.test(entry)) {
          files.push(full);
        }
      }
    }
    scanDir(matrixDir);

    expect(files.length).toBeGreaterThan(0);
    const evalImportPattern = /from\s+['"].*features\/evaluation.*['"]/;
    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      expect(
        evalImportPattern.test(content),
        `Found cross-feature import from evaluation in ${file}`,
      ).toBe(false);
    }
  });
});
