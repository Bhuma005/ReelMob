import { describe, it, expect } from 'vitest';
import { cn } from '../lib/utils';

describe('cn utility', () => {
  it('combines simple class names', () => {
    expect(cn('class1', 'class2')).toBe('class1 class2');
  });

  it('filters out falsy and null values', () => {
    expect(cn('class1', false, null, undefined, '', 'class2')).toBe('class1 class2');
  });

  it('resolves conflicting Tailwind utility classes properly via tailwind-merge', () => {
    // twMerge should ensure the latter padding overrides the former
    expect(cn('p-4', 'p-2')).toBe('p-2');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
  });

  it('handles array and object syntax', () => {
    expect(cn(['foo', 'bar'], { baz: true, qux: false })).toBe('foo bar baz');
  });
});
