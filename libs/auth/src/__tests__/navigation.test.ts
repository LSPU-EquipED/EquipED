import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { getCrossAppUrl } from '../navigation';

describe('getCrossAppUrl', () => {
  const originalLocation = window.location;

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  function mockLocation(port: string, hostname = 'localhost', protocol = 'http:') {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        port,
        hostname,
        protocol,
      },
    });
  }

  it('redirects to port 5174 when navigating from Faculty :5173 to admin routes', () => {
    mockLocation('5173');
    expect(getCrossAppUrl('/admin')).toBe('http://localhost:5174/admin');
    expect(getCrossAppUrl('/admin/users')).toBe('http://localhost:5174/admin/users');
    expect(getCrossAppUrl('/matrix')).toBe('http://localhost:5174/matrix');
    expect(getCrossAppUrl('/evaluation-map')).toBe('http://localhost:5174/evaluation-map');
  });

  it('redirects to port 5173 when navigating from Admin :5174 to faculty/auth routes', () => {
    mockLocation('5174');
    expect(getCrossAppUrl('/login')).toBe('http://localhost:5173/login');
    expect(getCrossAppUrl('/dashboard')).toBe('http://localhost:5173/dashboard');
    expect(getCrossAppUrl('/documents')).toBe('http://localhost:5173/documents');
    expect(getCrossAppUrl('/evaluations/123')).toBe('http://localhost:5173/evaluations/123');
  });

  it('preserves relative URLs when running on Caddy :3000 or production port', () => {
    mockLocation('3000');
    expect(getCrossAppUrl('/admin')).toBe('/admin');
    expect(getCrossAppUrl('/dashboard')).toBe('/dashboard');
    expect(getCrossAppUrl('/login')).toBe('/login');

    mockLocation(''); // default 80/443
    expect(getCrossAppUrl('/admin')).toBe('/admin');
    expect(getCrossAppUrl('/dashboard')).toBe('/dashboard');
  });
});
