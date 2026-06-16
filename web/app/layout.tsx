import type { Metadata } from 'next';
import { Toaster } from 'sonner';
// Theme tokens for the shared components, then the host's Tailwind layer.
import '@vibelevel/aura-ui/styles/aura-theme.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'Open Aura',
  description: 'Your local AI Aura — how you work with AI, from your real sessions.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Toaster theme="dark" position="bottom-center" />
      </body>
    </html>
  );
}
