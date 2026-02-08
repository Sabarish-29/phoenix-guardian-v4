/**
 * Admin User Management Page.
 *
 * Displays registered users, their roles, and the RBAC permission matrix.
 * Read-only for demo — user creation requires backend implementation.
 */

import React from 'react';

interface MockUser {
  id: number;
  name: string;
  email: string;
  role: string;
  status: 'active' | 'inactive';
  lastLogin: string;
}

const MOCK_USERS: MockUser[] = [
  { id: 1, name: 'System Admin', email: 'admin@phoenixguardian.health', role: 'admin', status: 'active', lastLogin: '2026-02-07T21:30:00Z' },
  { id: 2, name: 'Dr. Sarah Smith', email: 'dr.smith@phoenixguardian.health', role: 'physician', status: 'active', lastLogin: '2026-02-07T19:15:00Z' },
  { id: 3, name: 'Nurse Amy Jones', email: 'nurse.jones@phoenixguardian.health', role: 'nurse', status: 'active', lastLogin: '2026-02-07T18:45:00Z' },
];

const RBAC_MATRIX: { role: string; permissions: string[] }[] = [
  {
    role: 'Physician',
    permissions: ['Dashboard', 'New Encounter', 'SOAP Generator', 'Encounters List', 'Patient History', 'Orders', 'Drug Interactions'],
  },
  {
    role: 'Nurse',
    permissions: ['Dashboard', 'Encounters List', 'Triage', 'Patient History'],
  },
  {
    role: 'Admin',
    permissions: ['Security Console', 'Security Reports', 'User Management', 'Audit Logs', 'System Health'],
  },
  {
    role: 'Auditor',
    permissions: ['Audit Logs', 'Security Reports'],
  },
  {
    role: 'Read-Only',
    permissions: ['Dashboard (view only)'],
  },
];

const ROLE_BADGE: Record<string, string> = {
  admin: 'bg-red-100 text-red-700',
  physician: 'bg-blue-100 text-blue-700',
  nurse: 'bg-green-100 text-green-700',
  auditor: 'bg-purple-100 text-purple-700',
  readonly: 'bg-gray-100 text-gray-600',
};

export const AdminUsersPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">👥 User Management</h1>
        <p className="text-gray-500 mt-1 text-sm">View registered users and role-based access control settings</p>
      </div>

      {/* User Table */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Active Users ({MOCK_USERS.length})</h2>
          <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded">Read-only view</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500 text-xs uppercase">
              <th className="pb-2 pr-4">Name</th>
              <th className="pb-2 pr-4">Email</th>
              <th className="pb-2 pr-4">Role</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2">Last Login</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_USERS.map((u) => (
              <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 pr-4 font-medium text-gray-800">{u.name}</td>
                <td className="py-3 pr-4 text-gray-600 font-mono text-xs">{u.email}</td>
                <td className="py-3 pr-4">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold capitalize ${ROLE_BADGE[u.role] || ROLE_BADGE.readonly}`}>
                    {u.role}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span className={`inline-flex items-center gap-1 text-xs ${u.status === 'active' ? 'text-green-600' : 'text-gray-400'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${u.status === 'active' ? 'bg-green-500' : 'bg-gray-400'}`} />
                    {u.status === 'active' ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="py-3 text-gray-500 text-xs">{new Date(u.lastLogin).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* RBAC Permission Matrix */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Role-Based Access Control (RBAC)</h2>
        <p className="text-xs text-gray-500 mb-4">
          Permissions are enforced on both frontend (ProtectedRoute) and backend (require_admin / role checks).
          Users cannot escalate roles without database modification.
        </p>
        <div className="space-y-3">
          {RBAC_MATRIX.map((r) => (
            <div key={r.role} className="border border-gray-200 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${ROLE_BADGE[r.role.toLowerCase()] || 'bg-gray-100 text-gray-700'}`}>
                  {r.role}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {r.permissions.map((p) => (
                  <span key={p} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Security principle */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start gap-3">
        <span className="text-xl mt-0.5">🔐</span>
        <div>
          <h3 className="font-semibold text-blue-900 text-sm">Principle of Least Privilege</h3>
          <p className="text-xs text-blue-800 mt-1 leading-relaxed">
            Each role has the minimum permissions necessary to perform their duties.
            Admins cannot access clinical data. Physicians cannot access security settings.
            This follows HIPAA minimum necessary principle (45 CFR §164.502(b)) and
            NIST SP 800-53 Access Control (AC-6).
          </p>
        </div>
      </div>
    </div>
  );
};

export default AdminUsersPage;
