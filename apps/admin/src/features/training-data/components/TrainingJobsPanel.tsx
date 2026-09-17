import { useState } from 'react';
import { Button } from '@equiped/ui';
import { useStartTrainingJob } from '../hooks/useStartTrainingJob';
import { useTrainingJobs } from '../hooks/useTrainingJobs';
import type { TrainingJobCreateResponse } from '../types';

export function TrainingJobsPanel({ agentId }: { agentId: string }) {
  const { data } = useTrainingJobs(agentId);
  const startJob = useStartTrainingJob(agentId);
  const [lastCreated, setLastCreated] = useState<TrainingJobCreateResponse | null>(null);

  const handleStart = () => {
    startJob.mutate(undefined, {
      onSuccess: (result) => setLastCreated(result),
    });
  };

  return (
    <div className="space-y-4">
      <Button onClick={handleStart} disabled={startJob.isPending} isLoading={startJob.isPending}>
        {startJob.isPending ? 'Starting…' : 'Start Training Job'}
      </Button>

      {lastCreated && (
        <div className="rounded border border-border p-4 space-y-2 text-sm">
          <p>
            <strong>Download URL</strong> (paste into notebook cell 1, expires{' '}
            {new Date(lastCreated.download_expires_at).toLocaleString()}):
          </p>
          <code className="block break-all">{lastCreated.download_url}</code>
          <p>
            <strong>Upload URL</strong> (paste into notebook&apos;s last cell, expires{' '}
            {new Date(lastCreated.upload_expires_at).toLocaleString()}):
          </p>
          <code className="block break-all">{lastCreated.upload_url}</code>
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            <th>Job ID</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {(data?.jobs ?? []).map((job) => (
            <tr key={job.job_id}>
              <td>{job.job_id}</td>
              <td>{job.status}</td>
              <td>{new Date(job.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
