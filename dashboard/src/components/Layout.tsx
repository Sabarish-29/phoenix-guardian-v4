import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useState } from 'react';
import {
  HomeIcon,
  ShieldExclamationIcon,
  MapIcon,
  FingerPrintIcon,
  FolderArrowDownIcon,
  ExclamationTriangleIcon,
  Cog6ToothIcon,
  ChartBarIcon,
  Bars3Icon,
  XMarkIcon,
  BellIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline';
import { useAppSelector } from '../hooks/useStore';
import { selectConnectionStatus, selectUnreadAlerts } from '../store/slices/websocketSlice';
import clsx from 'clsx';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: number;
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Threat Feed', href: '/threats', icon: ShieldExclamationIcon },
  { name: 'Threat Map', href: '/map', icon: MapIcon },
  { name: 'Honeytokens', href: '/honeytokens', icon: FingerPrintIcon },
  { name: 'Evidence', href: '/evidence', icon: FolderArrowDownIcon },
  { name: 'Incidents', href: '/incidents', icon: ExclamationTriangleIcon },
  { name: 'Federated Intel', href: '/federated', icon: ChartBarIcon },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
];

/**
 * Main layout component with sidebar navigation and header
 */
export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const connectionStatus = useAppSelector(selectConnectionStatus);
  const unreadAlerts = useAppSelector(selectUnreadAlerts);

  const getPageTitle = () => {
    const currentNav = navigation.find(item => item.href === location.pathname);
    return currentNav?.name || 'Dashboard';
  };

  return (
    <div className="min-h-screen bg-dashboard-bg">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-64 bg-dashboard-card border-r border-dashboard-border transform transition-transform duration-200 ease-in-out lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-dashboard-border">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-phoenix-500 rounded-lg flex items-center justify-center">
              <ShieldExclamationIcon className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-semibold text-white">Phoenix Guardian</span>
          </div>
          <button
            className="lg:hidden text-dashboard-muted hover:text-white"
            onClick={() => setSidebarOpen(false)}
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-phoenix-500/20 text-phoenix-400'
                    : 'text-dashboard-muted hover:bg-dashboard-border hover:text-white'
                )}
                onClick={() => setSidebarOpen(false)}
              >
                <item.icon className="w-5 h-5 mr-3" />
                {item.name}
                {item.name === 'Threat Feed' && unreadAlerts > 0 && (
                  <span className="ml-auto bg-threat-critical text-white text-xs px-2 py-0.5 rounded-full">
                    {unreadAlerts > 99 ? '99+' : unreadAlerts}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Connection status */}
        <div className="px-4 py-3 border-t border-dashboard-border">
          <div className="flex items-center space-x-2">
            <span
              className={clsx(
                'status-dot',
                connectionStatus === 'connected' ? 'online' : 'offline'
              )}
            />
            <span className="text-sm text-dashboard-muted">
              {connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Header */}
        <header className="sticky top-0 z-30 flex items-center justify-between h-16 px-4 bg-dashboard-card border-b border-dashboard-border">
          <div className="flex items-center space-x-4">
            <button
              className="lg:hidden text-dashboard-muted hover:text-white"
              onClick={() => setSidebarOpen(true)}
            >
              <Bars3Icon className="w-6 h-6" />
            </button>
            <h1 className="text-xl font-semibold text-white">{getPageTitle()}</h1>
          </div>

          <div className="flex items-center space-x-4">
            {/* Alert bell */}
            <button className="relative text-dashboard-muted hover:text-white">
              <BellIcon className="w-6 h-6" />
              {unreadAlerts > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-threat-critical text-white text-xs rounded-full flex items-center justify-center">
                  {unreadAlerts > 9 ? '9+' : unreadAlerts}
                </span>
              )}
            </button>

            {/* User menu */}
            <button className="flex items-center space-x-2 text-dashboard-muted hover:text-white">
              <UserCircleIcon className="w-8 h-8" />
              <span className="hidden md:block text-sm">Security Admin</span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
