// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { Button } from '../Button';
import { Badge } from '../Badge';
import { Card, CardHeader, CardTitle, CardContent } from '../Card';
import { Input } from '../Input';

describe('Design System Primitives', () => {
  describe('Button', () => {
    it('renders with primary variant and default md size', () => {
      render(<Button>Submit</Button>);
      const btn = screen.getByRole('button', { name: /Submit/i }) as HTMLButtonElement;
      expect(btn).toBeDefined();
      expect(btn.className).toContain('bg-primary');
      expect(btn.className).toContain('h-10');
    });

    it('renders with secondary variant and sm size', () => {
      render(
        <Button variant="secondary" size="sm">
          Cancel
        </Button>,
      );
      const btn = screen.getByRole('button', { name: /Cancel/i }) as HTMLButtonElement;
      expect(btn.className).toContain('bg-surface');
      expect(btn.className).toContain('h-8');
    });

    it('disables button when isLoading is true', () => {
      render(<Button isLoading>Saving</Button>);
      const btn = screen.getByRole('button', { name: /Saving/i }) as HTMLButtonElement;
      expect(btn.disabled).toBe(true);
    });
  });

  describe('Badge', () => {
    it('renders status badges with appropriate semantic classes', () => {
      render(<Badge variant="success">Verified</Badge>);
      const badge = screen.getByText('Verified');
      expect(badge.className).toContain('bg-success-soft');
      expect(badge.className).toContain('text-success');
    });

    it('renders dot indicator when withDot is true', () => {
      const { container } = render(
        <Badge variant="warning" withDot>
          Pending
        </Badge>,
      );
      const dot = container.querySelector('.bg-warning');
      expect(dot).toBeDefined();
      expect(dot).not.toBeNull();
    });
  });

  describe('Card', () => {
    it('renders structured ledger card with header and title', () => {
      render(
        <Card variant="ledger">
          <CardHeader>
            <CardTitle>Evaluation Summary</CardTitle>
          </CardHeader>
          <CardContent>Content Area</CardContent>
        </Card>,
      );
      expect(screen.getByText('Evaluation Summary')).toBeDefined();
      expect(screen.getByText('Content Area')).toBeDefined();
    });
  });

  describe('Input', () => {
    it('renders label and handles hint text', () => {
      render(<Input label="Course Code" hint="E.g., ITEC 101" />);
      expect(screen.getByLabelText(/Course Code/i)).toBeDefined();
      expect(screen.getByText('E.g., ITEC 101')).toBeDefined();
    });

    it('renders error message with alert role', () => {
      render(<Input label="Course Code" error="Field is required" />);
      const errorMsg = screen.getByRole('alert');
      expect(errorMsg.textContent).toBe('Field is required');
      expect(errorMsg.className).toContain('text-destructive');
    });
  });
});
