import { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

const DAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const ACTIVITY_TYPES = ['resistance_training', 'cardio', 'hiit'];
const TRIGGER_OPTIONS = [
  { value: 'hard_low_glucose', label: 'Low Glucose' },
  { value: 'hard_high_hr', label: 'High Heart Rate' },
  { value: 'data_gap', label: 'CGM Data Gap' }
];

export default function UserProfile({ userId, showToast }) {
  const [profile, setProfile] = useState({
    name: '',
    birth_year: '',
    gender: 'male',
    weight_kg: '',
    height_cm: '',
    waist_cm: ''
  });
  
  const [bmi, setBmi] = useState(null);
  const [loading, setLoading] = useState(true);

  // ── Weekly Patterns state ──
  const [patterns, setPatterns] = useState([]);
  const [newPattern, setNewPattern] = useState({
    day_of_week: new Date().getDay() === 0 ? 6 : new Date().getDay() - 1,
    start_time: '14:00',
    end_time: '15:30',
    activity_type: 'resistance_training'
  });
  const [patternsLoading, setPatternsLoading] = useState(false);

  // ── Emergency contacts state ──
  const [emergencyContacts, setEmergencyContacts] = useState([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [newContact, setNewContact] = useState({
    contact_name: '',
    phone_number: '',
    relationship: '',
    notify_on: []
  });
  const [editingContactId, setEditingContactId] = useState(null);

  // Fetch initial data
  useEffect(() => {
    const fetchProfile = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/users/${userId}`);
        if (res.ok) {
          const data = await res.json();
          setProfile({
            name: data.name || '',
            birth_year: data.birth_year || '',
            gender: data.gender || 'male',
            weight_kg: data.weight_kg || '',
            height_cm: data.height_cm || '',
            waist_cm: data.waist_cm || ''
          });
          setBmi(data.bmi);
        } else {
          setProfile({ name: '', birth_year: '', gender: 'male', weight_kg: '', height_cm: '', waist_cm: '' });
          setBmi(null);
        }
      } catch (err) {
        showToast('Failed to load profile. Is Gateway running?', 'err');
      }
      setLoading(false);
    };
    fetchProfile();
    fetchPatterns();
    fetchEmergencyContacts();
  }, [userId]);

  // Fetch weekly patterns
  const fetchPatterns = async () => {
    setPatternsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/weekly-patterns`);
      if (res.ok) {
        const data = await res.json();
        setPatterns(data);
      }
    } catch (err) {
      // silent
    }
    setPatternsLoading(false);
  };

  // Handle inputs and live BMI calculation
  const handleChange = (e) => {
    const { name, value } = e.target;
    const newProfile = { ...profile, [name]: value };
    setProfile(newProfile);

    if ((name === 'weight_kg' || name === 'height_cm') || (newProfile.weight_kg && newProfile.height_cm)) {
      const w = parseFloat(name === 'weight_kg' ? value : newProfile.weight_kg);
      const h = parseFloat(name === 'height_cm' ? value : newProfile.height_cm) / 100;
      if (w > 0 && h > 0) {
        setBmi((w / (h * h)).toFixed(1));
      } else {
        setBmi(null);
      }
    }
  };

  const saveProfile = async () => {
    try {
      const payload = {};
      Object.keys(profile).forEach(k => {
        if (profile[k] !== '') {
          payload[k] = k === 'name' || k === 'gender' ? profile[k] : parseFloat(profile[k]);
        }
      });

      const res = await fetch(`${API_BASE}/users/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showToast('Profile saved successfully', 'ok');
      } else {
        showToast('Failed to save profile', 'err');
      }
    } catch (err) {
      showToast('Network error saving profile', 'err');
    }
  };

  // ── Weekly Pattern handlers ──

  const handlePatternChange = (e) => {
    const { name, value } = e.target;
    setNewPattern(prev => ({ ...prev, [name]: name === 'day_of_week' ? parseInt(value) : value }));
  };

  const addPattern = async () => {
    try {
      const payload = {
        day_of_week: newPattern.day_of_week,
        start_time: newPattern.start_time + ':00',
        end_time: newPattern.end_time + ':00',
        activity_type: newPattern.activity_type
      };

      const res = await fetch(`${API_BASE}/users/${userId}/weekly-patterns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        showToast('Weekly pattern added', 'ok');
        await fetchPatterns();
      } else {
        const err = await res.text();
        showToast(`Failed to add pattern: ${err}`, 'err');
      }
    } catch (err) {
      showToast('Network error adding pattern', 'err');
    }
  };

  const deletePattern = async (patternId) => {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/weekly-patterns/${patternId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        showToast('Pattern deleted', 'ok');
        await fetchPatterns();
      }
    } catch (err) {
      showToast('Failed to delete pattern', 'err');
    }
  };

  const fetchEmergencyContacts = async () => {
    setContactsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/emergency-contacts`);
      if (res.ok) {
        const data = await res.json();
        setEmergencyContacts(data);
      }
    } catch (err) {}
    setContactsLoading(false);
  };

  const handleContactChange = (e) => {
    const { name, value } = e.target;
    setNewContact(prev => ({ ...prev, [name]: value }));
  };

  const handleNotifyOnChange = (e) => {
    const { value, checked } = e.target;
    setNewContact(prev => {
      const notify_on = checked
        ? [...prev.notify_on, value]
        : prev.notify_on.filter(item => item !== value);
      return { ...prev, notify_on };
    });
  };

  const saveEmergencyContact = async () => {
    try {
      const isEditing = editingContactId !== null;
      const url = isEditing
        ? `${API_BASE}/users/${userId}/emergency-contacts/${editingContactId}`
        : `${API_BASE}/users/${userId}/emergency-contacts`;
      const method = isEditing ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newContact)
      });

      if (res.ok) {
        showToast(isEditing ? 'Emergency contact updated' : 'Emergency contact added', 'ok');
        setNewContact({ contact_name: '', phone_number: '', relationship: '', notify_on: [] });
        setEditingContactId(null);
        await fetchEmergencyContacts();
      } else {
        const err = await res.text();
        showToast(`Failed to save contact: ${err}`, 'err');
      }
    } catch (err) {
      showToast('Network error saving contact', 'err');
    }
  };

  const deleteEmergencyContact = async (contactId) => {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/emergency-contacts/${contactId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        showToast('Emergency contact deleted', 'ok');
        await fetchEmergencyContacts();
      }
    } catch (err) {
      showToast('Failed to delete contact', 'err');
    }
  };

  const editEmergencyContact = (contact) => {
    setEditingContactId(contact.id);
    setNewContact({
      contact_name: contact.contact_name,
      phone_number: contact.phone_number,
      relationship: contact.relationship || '',
      notify_on: contact.notify_on || []
    });
  };

  if (loading) return <div className="text-gray-500 animate-pulse">Loading profile...</div>;

  const getBmiBadge = () => {
    if (!bmi) return { label: 'N/A', bg: 'bg-gray-100 text-gray-500' };
    const b = parseFloat(bmi);
    if (b < 18.5) return { label: 'Underweight', bg: 'bg-blue-100 text-blue-700' };
    if (b < 25) return { label: 'Normal', bg: 'bg-green-100 text-green-700' };
    if (b < 30) return { label: 'Overweight', bg: 'bg-yellow-100 text-yellow-700' };
    return { label: 'Obese', bg: 'bg-red-100 text-red-700' };
  };

  const badge = getBmiBadge();

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">User Profile</h2>
      <p className="text-sm text-gray-500 mb-8 pb-4 border-b border-gray-100">
        Editing profile for <span className="font-mono text-purple-600 font-semibold">{userId}</span>. Changes are saved directly to the database.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
          <input type="text" name="name" value={profile.name} onChange={handleChange} className="w-full border border-gray-300 rounded-md px-4 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Birth Year</label>
          <input type="number" name="birth_year" value={profile.birth_year} onChange={handleChange} className="w-full border border-gray-300 rounded-md px-4 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
          <select name="gender" value={profile.gender} onChange={handleChange} className="w-full border border-gray-300 rounded-md px-4 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none bg-white">
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </div>

        <div>
           <label className="block text-sm font-medium text-gray-700 mb-1">Waist (cm)</label>
           <input type="number" name="waist_cm" value={profile.waist_cm} onChange={handleChange} className="w-full border border-gray-300 rounded-md px-4 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Height (cm)</label>
          <input type="number" name="height_cm" value={profile.height_cm} onChange={handleChange} className="w-full border border-gray-300 rounded-md px-4 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Weight (kg)</label>
          <input type="number" name="weight_kg" value={profile.weight_kg} onChange={handleChange} className="w-full border border-gray-300 rounded-md px-4 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
        </div>
      </div>

      <div className="bg-gray-50 rounded-lg p-5 flex items-center justify-between mb-8 border border-gray-100">
        <div>
          <p className="text-sm text-gray-500 font-medium uppercase tracking-wide">Calculated BMI</p>
          <div className="flex items-baseline space-x-3 mt-1">
            <span className="text-3xl font-bold text-gray-900">{bmi || '--'}</span>
            {bmi && (
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${badge.bg}`}>
                {badge.label}
              </span>
            )}
          </div>
        </div>
        <button 
          onClick={saveProfile}
          className="bg-purple-600 hover:bg-purple-700 text-white font-medium py-2 px-6 rounded-md shadow-sm transition-colors"
        >
          Save Profile
        </button>
      </div>

      {/* ── Weekly Activity Patterns ── */}
      <div className="border-t border-gray-200 pt-8 mt-4">
        <h3 className="text-lg font-semibold text-gray-800 mb-1">Weekly Activity Patterns</h3>
        <p className="text-sm text-gray-500 mb-5">
          Schedule recurring exercise sessions. The pre-exercise soft trigger checks this table to find upcoming activities.
        </p>

        {/* Existing Patterns Table */}
        <div className="bg-white border rounded-lg shadow-sm overflow-hidden mb-6">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">
              <tr>
                <th className="px-4 py-3">Day</th>
                <th className="px-4 py-3">Start</th>
                <th className="px-4 py-3">End</th>
                <th className="px-4 py-3">Activity</th>
                <th className="px-4 py-3 w-16"></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200 text-sm">
              {patternsLoading && (
                <tr><td colSpan="5" className="px-4 py-4 text-center text-gray-400 italic animate-pulse">Loading...</td></tr>
              )}
              {!patternsLoading && patterns.length === 0 && (
                <tr><td colSpan="5" className="px-4 py-6 text-center text-gray-400 italic">No weekly patterns configured.</td></tr>
              )}
              {patterns.map(p => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-700">{DAY_LABELS[p.day_of_week]}</td>
                  <td className="px-4 py-3 text-gray-600">{p.start_time}</td>
                  <td className="px-4 py-3 text-gray-600">{p.end_time}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">
                      {p.activity_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => deletePattern(p.id)}
                      className="text-red-400 hover:text-red-600 transition-colors text-xs font-medium"
                      title="Delete"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add New Pattern Form */}
        <div className="bg-indigo-50 rounded-lg p-5 border border-indigo-100">
          <h4 className="text-sm font-semibold text-indigo-800 mb-4 uppercase tracking-wide">Add New Pattern</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Day of Week</label>
              <select
                name="day_of_week"
                value={newPattern.day_of_week}
                onChange={handlePatternChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
              >
                {DAY_LABELS.map((label, idx) => (
                  <option key={idx} value={idx}>{label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Start Time</label>
              <input
                type="time"
                name="start_time"
                value={newPattern.start_time}
                onChange={handlePatternChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">End Time</label>
              <input
                type="time"
                name="end_time"
                value={newPattern.end_time}
                onChange={handlePatternChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Activity Type</label>
              <select
                name="activity_type"
                value={newPattern.activity_type}
                onChange={handlePatternChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
              >
                {ACTIVITY_TYPES.map(t => (
                  <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={addPattern}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-5 rounded-md shadow-sm transition-colors text-sm"
          >
            + Add Pattern
          </button>
        </div>
      </div>

      {/* ── Emergency Contacts ── */}
      <div className="border-t border-gray-200 pt-8 mt-8">
        <h3 className="text-lg font-semibold text-gray-800 mb-1">Emergency Contacts</h3>
        <p className="text-sm text-gray-500 mb-5">
          Configure who to notify in case of critical events.
        </p>

        {/* Existing Contacts Table */}
        <div className="bg-white border rounded-lg shadow-sm overflow-hidden mb-6">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">Relationship</th>
                <th className="px-4 py-3">Notify On</th>
                <th className="px-4 py-3 w-32"></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200 text-sm">
              {contactsLoading && (
                <tr><td colSpan="5" className="px-4 py-4 text-center text-gray-400 italic animate-pulse">Loading...</td></tr>
              )}
              {!contactsLoading && emergencyContacts.length === 0 && (
                <tr><td colSpan="5" className="px-4 py-6 text-center text-gray-400 italic">No emergency contacts configured.</td></tr>
              )}
              {emergencyContacts.map(c => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-700">{c.contact_name}</td>
                  <td className="px-4 py-3 text-gray-600">{c.phone_number}</td>
                  <td className="px-4 py-3 text-gray-600">{c.relationship || '-'}</td>
                  <td className="px-4 py-3 text-gray-600">
                    <div className="flex flex-wrap gap-1">
                      {(c.notify_on || []).map(t => (
                        <span key={t} className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">
                          {TRIGGER_OPTIONS.find(o => o.value === t)?.label || t}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => editEmergencyContact(c)}
                      className="text-indigo-600 hover:text-indigo-800 transition-colors text-xs font-medium mr-3"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => deleteEmergencyContact(c.id)}
                      className="text-red-400 hover:text-red-600 transition-colors text-xs font-medium"
                      title="Delete"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add/Edit Contact Form */}
        <div className="bg-red-50 rounded-lg p-5 border border-red-100 mb-6">
          <h4 className="text-sm font-semibold text-red-800 mb-4 uppercase tracking-wide">
            {editingContactId ? 'Edit Emergency Contact' : 'Add New Emergency Contact'}
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Contact Name *</label>
              <input
                type="text"
                name="contact_name"
                value={newContact.contact_name}
                onChange={handleContactChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Phone Number *</label>
              <input
                type="text"
                name="phone_number"
                value={newContact.phone_number}
                onChange={handleContactChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Relationship</label>
              <input
                type="text"
                name="relationship"
                value={newContact.relationship}
                onChange={handleContactChange}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 mb-2">Notify On</label>
            <div className="flex flex-wrap gap-4">
              {TRIGGER_OPTIONS.map(opt => (
                <label key={opt.value} className="flex items-center space-x-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    value={opt.value}
                    checked={newContact.notify_on?.includes(opt.value)}
                    onChange={handleNotifyOnChange}
                    className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex space-x-3">
            <button
              onClick={saveEmergencyContact}
              className="bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-5 rounded-md shadow-sm transition-colors text-sm"
            >
              {editingContactId ? 'Save Changes' : '+ Add Contact'}
            </button>
            {editingContactId && (
              <button
                onClick={() => {
                  setEditingContactId(null);
                  setNewContact({ contact_name: '', phone_number: '', relationship: '', notify_on: [] });
                }}
                className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium py-2 px-5 rounded-md shadow-sm transition-colors text-sm"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
