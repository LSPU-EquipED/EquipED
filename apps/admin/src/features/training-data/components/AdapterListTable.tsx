import { useTrainedAdapters } from '../hooks/useTrainedAdapters';

export function AdapterListTable({ agentId }: { agentId: string }) {
  const { data } = useTrainedAdapters(agentId);

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left">
          <th>Version</th>
          <th>Uploaded</th>
          <th>Size</th>
          <th>Hash</th>
          <th>Source Job</th>
        </tr>
      </thead>
      <tbody>
        {(data?.adapters ?? []).map((adapter) => (
          <tr key={adapter.adapter_id}>
            <td>{adapter.version}</td>
            <td>{new Date(adapter.created_at).toLocaleString()}</td>
            <td>{(adapter.size_bytes / (1024 * 1024)).toFixed(1)} MB</td>
            <td>{adapter.file_sha256.slice(0, 12)}…</td>
            <td>{adapter.job_id}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
