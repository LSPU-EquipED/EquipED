import { describe, expect, it } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

function getSourceFilesRecursively(dir: string): string[] {
  let results: string[] = [];
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    if (stat && stat.isDirectory()) {
      if (file === '__tests__') continue;
      results = results.concat(getSourceFilesRecursively(filePath));
    } else if (/\.(ts|tsx)$/.test(file) && !file.includes('.test.') && !file.includes('.spec.')) {
      results.push(filePath);
    }
  }
  return results;
}

describe('Evaluation Feature Boundaries', () => {
  it('evaluation feature never imports from upload feature directly', () => {
    const evaluationDir = path.resolve(__dirname, '../..');
    expect(path.basename(evaluationDir)).toBe('evaluation');

    const files = getSourceFilesRecursively(evaluationDir);
    expect(files.length).toBeGreaterThan(0);

    const uploadPattern = new RegExp(['from', "['\"].*features\\/upload.*['\"]"].join('\\s+'));
    const uploadImportPattern = new RegExp(['import', ".*['\"].*features\\/upload.*['\"]"].join('\\s+'));

    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      const hasUploadImport = uploadPattern.test(content) || uploadImportPattern.test(content);

      expect(hasUploadImport, `Found direct upload feature import in ${file}`).toBe(false);
    }
  });
});
