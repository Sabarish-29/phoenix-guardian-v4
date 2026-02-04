import { useState } from 'react';
import {
  BellIcon,
  PaintBrushIcon,
  ShieldCheckIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline';
import { useAppDispatch, useAppSelector } from '../hooks/useStore';
import {
  selectAlertSettings,
  selectDashboardSettings,
  selectNotificationSettings,
  updateAlertSettings,
  updateDashboardSettings,
  updateNotificationSettings,
} from '../store/slices/settingsSlice';
import clsx from 'clsx';

type SettingsTab = 'alerts' | 'display' | 'notifications' | 'profile';

/**
 * Settings - Dashboard configuration page
 */
export default function Settings() {
  const dispatch = useAppDispatch();
  const alertSettings = useAppSelector(selectAlertSettings);
  const dashboardSettings = useAppSelector(selectDashboardSettings);
  const notificationSettings = useAppSelector(selectNotificationSettings);
  
  const [activeTab, setActiveTab] = useState<SettingsTab>('alerts');

  const tabs: { id: SettingsTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'alerts', label: 'Alert Settings', icon: BellIcon },
    { id: 'display', label: 'Display', icon: PaintBrushIcon },
    { id: 'notifications', label: 'Notifications', icon: ShieldCheckIcon },
    { id: 'profile', label: 'Profile', icon: UserCircleIcon },
  ];

  return (
    <div className="max-w-4xl mx-auto">
      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-dashboard-border pb-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              activeTab === tab.id
                ? 'bg-phoenix-500/20 text-phoenix-400'
                : 'text-dashboard-muted hover:text-white hover:bg-dashboard-border'
            )}
          >
            <tab.icon className="w-5 h-5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Alert Settings */}
      {activeTab === 'alerts' && (
        <div className="space-y-6">
          <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Alert Channels</h3>
            <div className="space-y-4">
              <label className="flex items-center justify-between">
                <span className="text-dashboard-text">Email Notifications</span>
                <input
                  type="checkbox"
                  checked={alertSettings.emailEnabled}
                  onChange={(e) => dispatch(updateAlertSettings({ emailEnabled: e.target.checked }))}
                  className="w-5 h-5 rounded bg-dashboard-border border-dashboard-border text-phoenix-500 focus:ring-phoenix-500"
                />
              </label>
              <label className="flex items-center justify-between">
                <span className="text-dashboard-text">Slack Notifications</span>
                <input
                  type="checkbox"
                  checked={alertSettings.slackEnabled}
                  onChange={(e) => dispatch(updateAlertSettings({ slackEnabled: e.target.checked }))}
                  className="w-5 h-5 rounded bg-dashboard-border border-dashboard-border text-phoenix-500 focus:ring-phoenix-500"
                />
              </label>
              <label className="flex items-center justify-between">
                <span className="text-dashboard-text">SMS Notifications</span>
                <input
                  type="checkbox"
                  checked={alertSettings.smsEnabled}
                  onChange={(e) => dispatch(updateAlertSettings({ smsEnabled: e.target.checked }))}
                  className="w-5 h-5 rounded bg-dashboard-border border-dashboard-border text-phoenix-500 focus:ring-phoenix-500"
                />
              </label>
              <label className="flex items-center justify-between">
                <span className="text-dashboard-text">Critical Alerts Only</span>
                <input
                  type="checkbox"
                  checked={alertSettings.criticalOnly}
                  onChange={(e) => dispatch(updateAlertSettings({ criticalOnly: e.target.checked }))}
                  className="w-5 h-5 rounded bg-dashboard-border border-dashboard-border text-phoenix-500 focus:ring-phoenix-500"
                />
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Display Settings */}
      {activeTab === 'display' && (
        <div className="space-y-6">
          <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Dashboard Display</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-dashboard-text mb-2">Auto-Refresh Interval</label>
                <select
                  value={dashboardSettings.refreshInterval}
                  onChange={(e) => dispatch(updateDashboardSettings({ refreshInterval: Number(e.target.value) }))}
                  className="w-full px-4 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
                >
                  <option value={10}>10 seconds</option>
                  <option value={30}>30 seconds</option>
                  <option value={60}>1 minute</option>
                  <option value={300}>5 minutes</option>
                </select>
              </div>
              <label className="flex items-center justify-between">
                <span className="text-dashboard-text">Compact Mode</span>
                <input
                  type="checkbox"
                  checked={dashboardSettings.compactMode}
                  onChange={(e) => dispatch(updateDashboardSettings({ compactMode: e.target.checked }))}
                  className="w-5 h-5 rounded bg-dashboard-border border-dashboard-border text-phoenix-500 focus:ring-phoenix-500"
                />
              </label>
              <label className="flex items-center justify-between">
                <span className="text-dashboard-text">Show Animations</span>
                <input
                  type="checkbox"
                  checked={dashboardSettings.showAnimations}
                  onChange={(e) => dispatch(updateDashboardSettings({ showAnimations: e.target.checked }))}
                  className="w-5 h-5 rounded bg-dashboard-border border-dashboard-border text-phoenix-500 focus:ring-phoenix-500"
                />
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Notification Settings */}
      {activeTab === 'notifications' && (
        <div className="space-y-6">
          <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Browser Notifications</h3>
            <div className="space-y-4">
              <label className="flex items-center justify-between">
                <span className="text-dashboard-text">Sound Alerts</span>
                <input
                  type="checkbox"
                  checked={notificationSettings.sound}
                  onChange={(e) => dispatch(updateNotificationSettings({ sound: e.target.checked }))}
                  className="w-5 h-5 rounded bg-dashboard-border border-dashboard-border text-phoenix-500 focus:ring-phoenix-500"
                />
              </label>
              <label className="flex items-center justify-between">
                <span className="text-dashboard-text">Desktop Notifications</span>
                <input
                  type="checkbox"
                  checked={notificationSettings.desktop}
                  onChange={(e) => dispatch(updateNotificationSettings({ desktop: e.target.checked }))}
                  className="w-5 h-5 rounded bg-dashboard-border border-dashboard-border text-phoenix-500 focus:ring-phoenix-500"
                />
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Profile Settings */}
      {activeTab === 'profile' && (
        <div className="space-y-6">
          <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-6">
            <h3 className="text-lg font-semibold text-white mb-4">User Profile</h3>
            <div className="flex items-center gap-4 mb-6">
              <div className="w-16 h-16 bg-phoenix-500/20 rounded-full flex items-center justify-center">
                <UserCircleIcon className="w-10 h-10 text-phoenix-400" />
              </div>
              <div>
                <p className="text-white font-medium">Security Administrator</p>
                <p className="text-dashboard-muted text-sm">admin@hospital.org</p>
              </div>
            </div>
            <p className="text-dashboard-muted text-sm">
              Profile settings are managed through your organization's identity provider.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
