/**
 * Consistent alert color system for Phoenix Guardian V5.
 * 
 * Usage: import { ALERT_COLORS } from '../constants/alertColors'
 * Then use: ALERT_COLORS.critical.bg, ALERT_COLORS.critical.border, etc.
 */

export const ALERT_COLORS = {
  critical: {
    bg: 'bg-red-900/20',
    border: 'border-red-500',
    text: 'text-red-400',
    badge: 'bg-red-500',
    dot: 'bg-red-500 animate-pulse',
    icon: '🔴',
  },
  warning: {
    bg: 'bg-yellow-900/20',
    border: 'border-yellow-500',
    text: 'text-yellow-400',
    badge: 'bg-yellow-500',
    dot: 'bg-yellow-500',
    icon: '🟡',
  },
  watching: {
    bg: 'bg-blue-900/10',
    border: 'border-blue-800',
    text: 'text-blue-400',
    badge: 'bg-blue-700',
    dot: 'bg-blue-500',
    icon: '🔵',
  },
  clear: {
    bg: 'bg-green-900/10',
    border: 'border-green-800',
    text: 'text-green-400',
    badge: 'bg-green-700',
    dot: 'bg-green-500',
    icon: '🟢',
  },
  ghost: {
    bg: 'bg-gray-900/50',
    border: 'border-purple-500',
    text: 'text-purple-300',
    badge: 'bg-purple-600',
    dot: 'bg-purple-500 animate-pulse',
    icon: '👻',
  },
} as const;

export type AlertLevel = keyof typeof ALERT_COLORS;

export const getAlertColors = (level: string) => {
  return ALERT_COLORS[level as AlertLevel] || ALERT_COLORS.watching;
};
