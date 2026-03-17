import { useState } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

export default function DataInjector({ userId, showToast }) {
  const [cgm, setCgm] = useState({ glucose: 5.5 });
  const [hr, setHr] = useState({ heart_rate: 75, gps_lat: 1.3521, gps_lng: 103.8198 });
  const [exercise, setExercise] = useState({ exercise_type: 'resistance_training', duration_min: 45, avg_heart_rate: 140, calories_burned: 300 });
  const [emotion, setEmotion] = useState({ emotion_label: 'anxious', source: 'meralion' });

  const handleInject = async (endpoint, payload) => {
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        showToast(`Successfully injected to ${endpoint}`, 'ok');
      } else {
        showToast(`Failed injection: ${res.statusText}`, 'err');
      }
    } catch (err) {
      showToast(`Network error injecting to ${endpoint}`, 'err');
    }
  };

  const injectCGM = () => {
    handleInject('/telemetry/cgm', {
      user_id: userId,
      recorded_at: new Date().toISOString(),
      glucose: parseFloat(cgm.glucose)
    });
  };

  const injectHR = () => {
    handleInject('/telemetry/hr', {
      user_id: userId,
      recorded_at: new Date().toISOString(),
      heart_rate: parseInt(hr.heart_rate),
      gps_lat: parseFloat(hr.gps_lat),
      gps_lng: parseFloat(hr.gps_lng)
    });
  };

  const injectExercise = () => {
    const end = new Date();
    const start = new Date(end.getTime() - (exercise.duration_min * 60000));
    handleInject('/telemetry/exercise', {
      user_id: userId,
      exercise_type: exercise.exercise_type,
      started_at: start.toISOString(),
      ended_at: end.toISOString(),
      avg_heart_rate: parseInt(exercise.avg_heart_rate),
      calories_burned: parseFloat(exercise.calories_burned)
    });
  };

  const injectEmotion = () => {
    handleInject('/alerts/mental-health', {
      user_id: userId,
      emotion_label: emotion.emotion_label,
      source: emotion.source,
      timestamp: new Date().toISOString()
    });
  };

  const triggerDataGap = () => {
    handleInject('/test/check-data-gap', { user_id: userId });
  };

  return (
    <div className="max-w-4xl space-y-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Manual Data Injector</h2>
        <p className="text-sm text-gray-500 mt-1">Send synthetic telemetry to the Gateway API for testing triggers.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CGM Card */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-800">CGM Reading</h3>
            <span className="text-xs font-mono bg-purple-100 text-purple-700 px-2 py-1 rounded">POST /telemetry/cgm</span>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Glucose Level (mmol/L)</label>
              <input type="number" step="0.1" value={cgm.glucose} onChange={e => setCgm({...cgm, glucose: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
            </div>
            <button onClick={injectCGM} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-md transition-colors">Inject CGM</button>
          </div>
        </div>

        {/* HR & GPS Card */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-800">Heart Rate & GPS</h3>
            <span className="text-xs font-mono bg-purple-100 text-purple-700 px-2 py-1 rounded">POST /telemetry/hr</span>
          </div>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Heart Rate (bpm)</label>
              <input type="number" value={hr.heart_rate} onChange={e => setHr({...hr, heart_rate: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">GPS Lat</label>
              <input type="number" step="0.0001" value={hr.gps_lat} onChange={e => setHr({...hr, gps_lat: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">GPS Lng</label>
              <input type="number" step="0.0001" value={hr.gps_lng} onChange={e => setHr({...hr, gps_lng: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
            </div>
          </div>
          <button onClick={injectHR} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-md transition-colors">Inject HR Data</button>
        </div>

        {/* Exercise Session Card */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-800">Exercise Session</h3>
            <span className="text-xs font-mono bg-purple-100 text-purple-700 px-2 py-1 rounded">POST /telemetry/exercise</span>
          </div>
          <div className="space-y-3 mb-4">
            <select value={exercise.exercise_type} onChange={e => setExercise({...exercise, exercise_type: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none bg-white">
              <option value="resistance_training">Resistance Training</option>
              <option value="cardio">Cardio</option>
              <option value="hiit">HIIT</option>
            </select>
            <div className="grid grid-cols-2 gap-3">
              <div>
                 <label className="block text-xs font-medium text-gray-500 mb-1">Duration (min)</label>
                 <input type="number" value={exercise.duration_min} onChange={e => setExercise({...exercise, duration_min: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:outline-none" />
              </div>
              <div>
                 <label className="block text-xs font-medium text-gray-500 mb-1">Calories</label>
                 <input type="number" value={exercise.calories_burned} onChange={e => setExercise({...exercise, calories_burned: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:outline-none" />
              </div>
            </div>
          </div>
          <button onClick={injectExercise} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-md transition-colors">Inject Exercise</button>
        </div>

        {/* Emotion Alert Card */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-800">Emotion Alert</h3>
            <span className="text-xs font-mono bg-purple-100 text-purple-700 px-2 py-1 rounded">POST /alerts/mental-health</span>
          </div>
          <div className="space-y-3 mb-4 mt-2">
            <select value={emotion.emotion_label} onChange={e => setEmotion({...emotion, emotion_label: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none bg-white">
              <option value="anxious">Anxious</option>
              <option value="stressed">Stressed</option>
              <option value="calm">Calm</option>
            </select>
            <input type="text" placeholder="Source (e.g. meralion)" value={emotion.source} onChange={e => setEmotion({...emotion, source: e.target.value})} className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:outline-none" />
          </div>
          <button onClick={injectEmotion} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 rounded-md transition-colors mt-4">Inject Emotion</button>
        </div>

        {/* Data Gap Trigger */}
        <div className="bg-red-50 border border-red-200 rounded-lg p-5 shadow-sm col-span-1 lg:col-span-2 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-red-800 flex items-center">
              Force Data-Gap Check
              <span className="ml-3 text-xs font-mono bg-red-100 text-red-700 px-2 py-1 rounded border border-red-200">POST /test/check-data-gap</span>
            </h3>
            <p className="text-sm text-red-600 mt-1">Triggers evaluation of missing CGM data (Demo mode only).</p>
          </div>
          <button onClick={triggerDataGap} className="bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-6 rounded-md transition-colors">Test Gap Trigger</button>
        </div>

      </div>
    </div>
  );
}
