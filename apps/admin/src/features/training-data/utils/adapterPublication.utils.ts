import type { TrainedAdapterListResponse } from '../types';

export function getPublishedAdapterWarning(
  data: TrainedAdapterListResponse | undefined,
): string | null {
  const publishedAdapter = data?.adapters.find((adapter) => adapter.published);
  if (!publishedAdapter) return null;
  if (data?.server_reachable === false) {
    return `The model server could not be reached, so it is unknown whether published fine-tuned model v${publishedAdapter.version} is loaded.`;
  }
  if (publishedAdapter.loaded === false) {
    return `Published fine-tuned model v${publishedAdapter.version} is not loaded on the model server. Ask IT staff to add it using the steps under that model, then restart the server.`;
  }
  return null;
}
