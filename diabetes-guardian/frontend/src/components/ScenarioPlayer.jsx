import { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

const SCENARIOS = [
  'hard_trigger_data_gap.json',
  'hard_trigger_high_hr.json',
  'hard_trigger_low_glucose.json',
  'no_trigger.json',
  'soft_trigger_pre_exercise.json',
  'soft_trigger_slope.json',
  'soft_trigger_reflector_reject.json'
];

export default function ScenarioPlayer({ userId, showToast }) {
  const [selectedFile, setSelectedFile] = useState(SCENARIOS[0]);
  const [scenario, setScenario] = useState(null);
  const [logs, setLogs] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [interventions, setInterventions] = useState([]);

  // Load the scenario definition
  useEffect(() => {
    const fetchScenario = async () => {
      try {
        const res = await fetch(`/scenarios/${selectedFile}`);
        if (res.ok) {
          const data = await res.json();
          setScenario(data);
        }
      } catch (err) {
        showToast('Error loading scenario file.', 'err');
      }
    };
    fetchScenario();
  }, [selectedFile]);

  // Poll for agent interventions
  useEffect(() => {
    let interval;
    if (isPlaying) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/users/${userId}/intervention-log?limit=5`);
          if (res.ok) {
            const data = await res.json();
            setInterventions(data);
          }
        } catch (e) {}
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [isPlaying, userId]);

  const addLog = (msg, isError = false) => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), msg, isError }]);
  };

  const playScenario = async () => {
    if (!scenario || !scenario.steps) return;
    
    setIsPlaying(true);
    setLogs([]);
    addLog(`Starting scenario: ${scenario.scenario_id}`);
    
    const baseTime = new Date();
    
    for (let i = 0; i < scenario.steps.length; i++) {
        const step = scenario.steps[i];
        const [method, path] = step.endpoint.split(' ');
        
        // Calculate the timestamp for this step
        const stepTime = new Date(baseTime.getTime() + (step.offset_minutes * 60000));
        
        // Inject dynamic attributes
        const payload = { ...step.body, user_id: userId };
        
        // Generate local ISO string (NOT UTC) so DEMO_MODE reference_time matches local clock
        const toLocalISO = (d) => {
            const pad = (n) => String(n).padStart(2, '0');
            return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
        };

        // Only endpoints that expect recorded_at should get it.
        if (path === '/telemetry/cgm' || path === '/telemetry/hr') {
            payload.recorded_at = toLocalISO(stepTime);
        } else if (path === '/telemetry/exercise') {
             payload.ended_at = toLocalISO(stepTime);
             payload.started_at = toLocalISO(new Date(stepTime.getTime() - 3600000));
        } else if (path === '/alerts/mental-health') {
             payload.timestamp = toLocalISO(stepTime);
        }

        addLog(`Executing Step ${i+1}/${scenario.steps.length}: 
                [${method}] ${path} (Offset: +${step.offset_minutes}m)`);
        
        try {
            const res = await fetch(`${API_BASE}${path}`, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!res.ok) {
                addLog(`Step ${i+1} failed: ${res.statusText}`, true);
            }
        } catch (err) {
            addLog(`Network error on step ${i+1}`, true);
        }

        // Artificial delay so UI feels like it's playing
        if (i < scenario.steps.length - 1) {
            await new Promise(r => setTimeout(r, 600));
        }
    }
    
    // Determine wait time based on scenario type
    const isSoftTrigger = scenario.scenario_id?.startsWith('soft_trigger');
    const waitMs = isSoftTrigger ? 30000 : 3000;
    
    if (isSoftTrigger) {
        addLog('Scenario execution completed. Waiting for Celery/Agent to process...');
    } else {
        addLog('Scenario execution completed. Checking results...');
    }
    
    setTimeout(() => {
        setIsPlaying(false);
        addLog(isSoftTrigger ? 'Finished waiting for background agent.' : 'Done.');
    }, waitMs);
  };

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Scenario Player</h2>
          <p className="text-sm text-gray-500 mt-1">Play pre-defined demo scripts and trace the system's response.</p>
        </div>
        <select 
          value={selectedFile} 
          onChange={e => setSelectedFile(e.target.value)}
          className="bg-white border text-sm border-gray-300 rounded-md px-4 py-2 focus:ring-2 focus:ring-purple-500 outline-none min-w-[240px]"
        >
          {SCENARIOS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        
        {/* Scenario Details Panel */}
        <div className="bg-purple-50 rounded-lg p-5 border border-purple-100">
          <h3 className="font-semibold text-purple-900 mb-2">{scenario ? scenario.scenario_id : 'Loading...'}</h3>
          <p className="text-sm text-purple-800 mb-2"><strong>Description:</strong> {scenario?.description}</p>
          <p className="text-sm text-purple-800 mb-4"><strong>Expected:</strong> {scenario?.expected_outcome}</p>
          
          <div className="bg-white rounded p-3 text-xs font-mono text-gray-700 h-48 overflow-y-auto outline-none border border-purple-200">
            {scenario ? JSON.stringify(scenario.steps, null, 2) : ''}
          </div>
          
          <div className="flex gap-4 mt-4">
            <button 
              onClick={playScenario} 
              disabled={isPlaying}
              className={`flex-1 font-bold py-3 rounded shadow transition-colors flex justify-center items-center ${
                  isPlaying ? 'bg-gray-400 text-white cursor-not-allowed' : 'bg-green-500 hover:bg-green-600 text-white'
              }`}
            >
              {isPlaying ? (
                  <><span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin mr-2"></span> Playing...</>
              ) : '▶ Play Scenario'}
            </button>
            <button 
              onClick={async () => {
                if (!window.confirm("Are you sure you want to delete all of today's test data (CGM, HR, Exercise, Interventions) for this user?")) return;
                try {
                  const res = await fetch(`${API_BASE}/test/reset-today`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId })
                  });
                  if (res.ok) {
                    const data = await res.json();
                    showToast(`Success! Deleted ${data.total_deleted} items across tables.`, 'ok');
                    addLog(`[Reset] Deleted today's data: ${JSON.stringify(data.deleted)}`);
                  } else {
                    showToast('Failed to reset today\'s data', 'err');
                  }
                } catch (err) {
                  showToast('Network error during reset', 'err');
                }
              }}
              disabled={isPlaying}
              className={`font-semibold py-3 px-4 rounded shadow border transition-colors ${
                  isPlaying ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed' : 'bg-white hover:bg-red-50 text-red-600 border-red-200'
              }`}
              title="Deletes CGM, HR, Exercise, and Intervention logs for TODAY ONLY."
            >
              🗑️ Reset Today
            </button>
          </div>
        </div>

        {/* Console Execution Log */}
        <div className="bg-gray-900 rounded-lg flex flex-col overflow-hidden shadow-inner font-mono text-sm h-[400px]">
          <div className="bg-gray-800 px-4 py-2 border-b border-gray-700 flex justify-between items-center text-gray-400 text-xs tracking-wider uppercase">
             <span>Execution Trace</span>
             {isPlaying && <span className="text-green-400 animate-pulse">● Live</span>}
          </div>
          <div className="flex-1 p-4 overflow-y-auto space-y-2">
             {logs.length === 0 && <span className="text-gray-600 italic">Ready to run scenario...</span>}
             {logs.map((L, i) => (
                 <div key={i} className={`${L.isError ? 'text-red-400' : 'text-green-300'}`}>
                    <span className="text-gray-500 mr-2">[{L.time}]</span> 
                    {L.msg}
                 </div>
             ))}
          </div>
        </div>
      </div>

      {/* Backend Agent Reaction */}
      <div>
         <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
             Agent Interventions 
             {(isPlaying) && <span className="ml-3 text-xs font-normal text-purple-600 bg-purple-100 px-2 py-0.5 rounded-full animate-pulse">Polling Celery...</span>}
         </h3>
         
         <div className="bg-white border rounded shadow-sm overflow-hidden">
             <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">
                    <tr>
                        <th className="px-6 py-3">Time</th>
                        <th className="px-6 py-3">Trigger Type</th>
                        <th className="px-6 py-3">Agent Decision</th>
                        <th className="px-6 py-3">Notification</th>
                    </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200 text-sm">
                    {interventions.length === 0 && (
                        <tr>
                            <td colSpan="4" className="px-6 py-8 text-center text-gray-500 italic">No interventions found in recent log.</td>
                        </tr>
                    )}
                    {interventions.map(i => (
                        <tr key={i.id} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-gray-700">{new Date(i.triggered_at).toLocaleTimeString()}</td>
                            <td className="px-6 py-4">
                                <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${(i.trigger_type.startsWith('hard_') || i.trigger_type === 'data_gap') ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'}`}>
                                    {i.display_label || i.trigger_type}
                                </span>
                            </td>
                            <td className="px-6 py-4 text-gray-800 font-medium">{i.agent_decision || '-'}</td>
                            <td className="px-6 py-4 text-gray-500">{i.message_sent || '-'}</td>
                        </tr>
                    ))}
                </tbody>
             </table>
         </div>
      </div>
    </div>
  );
}
