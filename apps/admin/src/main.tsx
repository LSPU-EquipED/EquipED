import { createRoot } from 'react-dom/client';
import { lspuLogoUrl } from '@equiped/ui';
import { AppProviders } from './app/providers';
import './app.css';

const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
if (favicon) {
  favicon.href = lspuLogoUrl;
}

const root = document.getElementById('root');

if (!root) {
  throw new Error('Missing #root element. The app cannot boot without a mount point.');
}

createRoot(root).render(<AppProviders />);
