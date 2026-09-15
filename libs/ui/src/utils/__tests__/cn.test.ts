import { describe, it, expect } from 'vitest';
import { cn } from '../cn';

describe('cn utility', () => {
  it('combines class names correctly', () => {
    expect(cn('class1', 'class2')).toBe('class1 class2');
  });

  it('filters out falsy values', () => {
    expect(cn('class1', undefined, null, false, 'class2')).toBe('class1 class2');
  });
});
