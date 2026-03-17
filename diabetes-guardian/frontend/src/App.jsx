import { useState } from 'react';
import UserProfile from './components/UserProfile';
import DataInjector from './components/DataInjector';
import ScenarioPlayer from './components/ScenarioPlayer';

export default function App() {
  const [userId, setUserId] = useState('user_001');
  const [activeTab, setActiveTab] = useState('profile');
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'ok') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      {/* Toast Notification */}
      {toast && (
        <div className={`fixed top-4 right-4 px-4 py-3 rounded shadow-lg text-white font-medium z-50 transition-opacity ${
          toast.type === 'ok' ? 'bg-green-500' :
          toast.type === 'warn' ? 'bg-yellow-500' : 'bg-red-500'
        }`}>
          {toast.message}
        </div>
      )}

      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center space-x-3">
          <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
          <h1 className="text-xl font-semibold text-gray-800 tracking-tight">Diabetes Guardian Test Dashboard</h1>
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm font-medium text-gray-600">Active User:</label>
          <input 
            type="text" 
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm w-40"
          />
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 max-w-7xl mx-auto w-full px-6 py-8 flex flex-col md:flex-row gap-8">
        
        {/* Sidebar Nav */}
        <nav className="w-full md:w-64 flex-shrink-0">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            <button 
              onClick={() => setActiveTab('profile')}
              className={`w-full text-left px-5 py-4 text-sm font-medium transition-colors border-b border-gray-100 ${
                activeTab === 'profile' ? 'bg-purple-50 text-purple-700 border-l-4 border-l-purple-600' : 'text-gray-600 hover:bg-gray-50 border-l-4 border-l-transparent'
              }`}
            >
              User Profile
            </button>
            <button 
              onClick={() => setActiveTab('injector')}
              className={`w-full text-left px-5 py-4 text-sm font-medium transition-colors border-b border-gray-100 ${
                activeTab === 'injector' ? 'bg-purple-50 text-purple-700 border-l-4 border-l-purple-600' : 'text-gray-600 hover:bg-gray-50 border-l-4 border-l-transparent'
              }`}
            >
              Manual Data Injector
            </button>
            <button 
              onClick={() => setActiveTab('scenarios')}
              className={`w-full text-left px-5 py-4 text-sm font-medium transition-colors ${
                activeTab === 'scenarios' ? 'bg-purple-50 text-purple-700 border-l-4 border-l-purple-600' : 'text-gray-600 hover:bg-gray-50 border-l-4 border-l-transparent'
              }`}
            >
              Scenario Player
            </button>
          </div>
        </nav>

        {/* Tab Content */}
        <main className="flex-1 bg-white rounded-lg shadow-sm border border-gray-200 p-8 min-h-[600px]">
          {activeTab === 'profile' && <UserProfile userId={userId} showToast={showToast} />}
          {activeTab === 'injector' && <DataInjector userId={userId} showToast={showToast} />}
          {activeTab === 'scenarios' && <ScenarioPlayer userId={userId} showToast={showToast} />}
        </main>
      </div>
    </div>
  );
}
