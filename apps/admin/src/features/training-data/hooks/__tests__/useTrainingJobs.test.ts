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
