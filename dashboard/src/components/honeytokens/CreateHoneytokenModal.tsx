import { useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { useAppDispatch } from '../../hooks/useStore';
import { createHoneytoken } from '../../store/slices/honeytokensSlice';
import type { HoneytokenType } from '../../types/honeytoken';

interface CreateHoneytokenModalProps {
  onClose: () => void;
}

const honeytokenTypes: { value: HoneytokenType; label: string; description: string }[] = [
  { value: 'patient_record', label: 'Patient Record', description: 'Fake patient health record' },
  { value: 'medication', label: 'Medication', description: 'Fake medication or prescription data' },
  { value: 'admin_credential', label: 'Admin Credential', description: 'Fake admin username/password' },
  { value: 'api_key', label: 'API Key', description: 'Fake API key or token' },
  { value: 'database', label: 'Database', description: 'Fake database connection or table' },
];

/**
 * Modal for creating a new honeytoken
 */
export default function CreateHoneytokenModal({ onClose }: CreateHoneytokenModalProps) {
  const dispatch = useAppDispatch();
  const [name, setName] = useState('');
  const [type, setType] = useState<HoneytokenType>('patient_record');
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await dispatch(createHoneytoken({
        name,
        type,
        description,
        location,
        status: 'active',
        triggerCount: 0,
        alertLevel: 'high',
      }));
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-dashboard-card rounded-xl border border-dashboard-border w-full max-w-lg">
        <div className="flex items-center justify-between p-4 border-b border-dashboard-border">
          <h2 className="text-lg font-semibold text-white">Create Honeytoken</h2>
          <button onClick={onClose} className="text-dashboard-muted hover:text-white">
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm text-dashboard-muted mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
              placeholder="e.g., VIP Patient Record"
            />
          </div>

          <div>
            <label className="block text-sm text-dashboard-muted mb-1">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as HoneytokenType)}
              className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
            >
              {honeytokenTypes.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label} - {t.description}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-dashboard-muted mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
              placeholder="Describe this honeytoken..."
            />
          </div>

          <div>
            <label className="block text-sm text-dashboard-muted mb-1">Location</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full px-3 py-2 bg-dashboard-bg border border-dashboard-border rounded-lg text-white focus:outline-none focus:border-phoenix-500"
              placeholder="e.g., /data/patients/vip"
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-dashboard-muted hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !name}
              className="px-4 py-2 bg-phoenix-500 text-white rounded-lg hover:bg-phoenix-600 transition-colors disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Honeytoken'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
