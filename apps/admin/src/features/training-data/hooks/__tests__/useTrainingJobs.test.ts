import { describe, expect, it } from 'vitest';
import { jobsRefetchInterval } from '../useTrainingJobs';

const data = (stages: (string | undefined)[]) => ({
  agent_id: 'sme',
  jobs: stages.map((run_stage, i) => ({
    job_id: String(i),
    agent_id: 'sme',
    status: 'downloaded',
    created_at: 'x',
    run_stage,
  })),
});

describe('jobsRefetchInterval', () => {
  it('polls every 10 seconds while a run is active', () => {
    expect(jobsRefetchInterval(data(['finished', 'training']) as never)).toBe(10_000);
  });
  it('stops polling when nothing is active', () => {
    expect(jobsRefetchInterval(data(['finished', 'failed', undefined]) as never)).toBe(false);
    expect(jobsRefetchInterval(undefined)).toBe(false);
  });
});

const NOW = Date.parse('2026-10-10T12:00:00Z');
const HOUR = 3600_000;
const iso = (agoMs: number) => new Date(NOW - agoMs).toISOString();
const one = (job: Record<string, unknown>) => ({
  agent_id: 'sme',
  jobs: [{ job_id: 'j', agent_id: 'sme', status: 'downloaded', ...job }],
});

describe('jobsRefetchInterval with a clock', () => {
  it('polls a fresh run that has not reported a stage yet', () => {
    expect(jobsRefetchInterval(one({ created_at: iso(5 * 60_000) }) as never, NOW)).toBe(10_000);
    expect(
      jobsRefetchInterval(one({ created_at: iso(5 * 60_000), status: 'pending' }) as never, NOW),
    ).toBe(10_000);
  });
  it('stops waiting for a run with no stage once it is older than 24 hours', () => {
    expect(jobsRefetchInterval(one({ created_at: iso(25 * HOUR) }) as never, NOW)).toBe(false);
  });
  it('does not poll a completed job with no stage', () => {
    expect(
      jobsRefetchInterval(one({ created_at: iso(HOUR), status: 'completed' }) as never, NOW),
    ).toBe(false);
  });
  it('polls an active run that reported recently', () => {
    const job = { created_at: iso(HOUR), run_stage: 'training', seconds_since_report: 600 };
    expect(jobsRefetchInterval(one(job) as never, NOW)).toBe(10_000);
  });
  it('gives up on a run that has been silent for 2 hours', () => {
    const job = { created_at: iso(5 * HOUR), run_stage: 'training', seconds_since_report: 7200 };
    expect(jobsRefetchInterval(one(job) as never, NOW)).toBe(false);
  });
  it('gives up on a run older than the 7-day token lifetime', () => {
    const job = {
      created_at: iso(8 * 24 * HOUR),
      run_stage: 'converting',
      seconds_since_report: 10,
    };
    expect(jobsRefetchInterval(one(job) as never, NOW)).toBe(false);
  });
  it('does not poll finished or failed runs', () => {
    for (const run_stage of ['finished', 'failed']) {
      const job = { created_at: iso(HOUR), run_stage, seconds_since_report: 1 };
      expect(jobsRefetchInterval(one(job) as never, NOW)).toBe(false);
    }
  });
  it('does not wait for a stage-less run whose created_at is unreadable', () => {
    expect(jobsRefetchInterval(one({ created_at: 'x' }) as never, NOW)).toBe(false);
  });
  it('still polls a recently reporting run whose created_at is unreadable', () => {
    const job = { created_at: 'x', run_stage: 'training', seconds_since_report: 5 };
    expect(jobsRefetchInterval(one(job) as never, NOW)).toBe(10_000);
  });
});
