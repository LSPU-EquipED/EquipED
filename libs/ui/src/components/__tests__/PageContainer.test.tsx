// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { PageContainer } from '../PageContainer';

describe('PageContainer', () => {
  it('renders as section by default with standard shell container classes', () => {
    render(<PageContainer data-testid="container">Content</PageContainer>);
    const el = screen.getByTestId('container');
    expect(el.tagName).toBe('SECTION');
    expect(el.className).toContain('max-w-[108rem]');
    expect(el.className).toContain('mx-auto');
    expect(el.textContent).toBe('Content');
  });

  it('renders custom semantic element when "as" prop is provided', () => {
    render(
      <PageContainer as="main" data-testid="main-container">
        Main content
      </PageContainer>,
    );
    const el = screen.getByTestId('main-container');
    expect(el.tagName).toBe('MAIN');
  });

  it('merges custom className with tailwind merge', () => {
    render(
      <PageContainer className="space-y-4 py-4" data-testid="custom-container">
        Custom
      </PageContainer>,
    );
    const el = screen.getByTestId('custom-container');
    expect(el.className).toContain('space-y-4');
    expect(el.className).toContain('py-4');
  });
});
