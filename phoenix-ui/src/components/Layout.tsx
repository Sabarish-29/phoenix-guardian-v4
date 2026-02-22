/**
 * Main layout component with header and content area.
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';

interface LayoutProps {
  children?: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-deep)' }}>
      <Header />
      <main style={{ maxWidth: '1280px', margin: '0 auto', padding: '32px 16px', paddingBottom: 60 }}>
        {children || <Outlet />}
      </main>

      {/* Privacy & Compliance Footer */}
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: 28,
        background: 'rgba(5,10,18,0.95)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 24,
        zIndex: 100,
        backdropFilter: 'blur(8px)'
      }}>
        {[
          { icon: '🔒', text: 'Data stays hospital-local' },
          { icon: '📋', text: 'DPDP Act 2023 compliant' },
          { icon: '🔍', text: 'All decisions audit-logged' },
          { icon: '⚕️', text: 'Clinical decision support only — not a diagnosis' }
        ].map((item, i) => (
          <div key={i} style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: '0.65rem',
            color: '#4a5568',
            whiteSpace: 'nowrap'
          }}>
            <span style={{ fontSize: '0.65rem' }}>{item.icon}</span>
            <span>{item.text}</span>
            {i < 3 && (
              <span style={{
                marginLeft: 24,
                color: 'rgba(255,255,255,0.08)'
              }}>|</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Layout;
