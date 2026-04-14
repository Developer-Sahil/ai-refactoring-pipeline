import { useState } from 'react';
import './App.css';

function App() {
  const [inPlace, setInPlace] = useState(false);
  const [batchSize, setBatchSize] = useState(1);
  const [delay, setDelay] = useState(0);
  const [model, setModel] = useState('gemini-2.5-flash');
  
  // Stages: 0: idle, 1: cast, 2: prompt, 3: llm, 4: validator, 5: done
  const [pipelineStage, setPipelineStage] = useState(0); 

  const handleRunRefactor = () => {
    // Dummy animation for pipeline
    setPipelineStage(1);
    setTimeout(() => setPipelineStage(2), 1500);
    setTimeout(() => setPipelineStage(3), 3000);
    setTimeout(() => setPipelineStage(4), 5000);
    setTimeout(() => setPipelineStage(5), 6500);
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar neu-raised">
        <div className="logo">
          <div className="logo-icon neu-inset">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="16 18 22 12 16 6"></polyline>
              <polyline points="8 6 2 12 8 18"></polyline>
            </svg>
          </div>
          SDP Refactor
        </div>
        
        <nav className="nav-links">
          <div className="nav-item active neu-inset">Dashboard</div>
          <div className="nav-item">History</div>
          <div className="nav-item">Settings</div>
        </nav>
      </aside>

      {/* Main Workspace */}
      <main className="main-content">
        <header className="header">
          <div>
            <h2>Refactoring Dashboard</h2>
            <p style={{ color: 'var(--text-color-muted)' }}>Upload your codebase to let AI structure and refactor it.</p>
          </div>
          <div className="user-profile neu-raised">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
          </div>
        </header>

        <div className="dashboard-grid">
          {/* Left Column */}
          <div>
            <div className="upload-card neu-raised">
              <h3>Source Code</h3>
              <div className="drop-zone neu-inset">
                <div className="drop-icon">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="17 8 12 3 7 8"></polyline>
                    <line x1="12" y1="3" x2="12" y2="15"></line>
                  </svg>
                </div>
                <h4>Drag & Drop files or directories here</h4>
                <p>or click to browse</p>
                <button className="neu-button" style={{ marginTop: '16px' }}>Select Files</button>
              </div>
            </div>

            {/* Pipeline State Overlay (showing only if started) */}
            {(pipelineStage > 0) && (
              <div className="pipeline-card neu-raised">
                <h3>Pipeline Status</h3>
                <div className="steps">
                  {/* Step 1: cAST */}
                  <div className={`step neu-raised ${pipelineStage > 1 ? 'completed' : pipelineStage === 1 ? 'active' : ''}`}>1</div>
                  {/* Step 2: Prompt Builder */}
                  <div className={`step neu-raised ${pipelineStage > 2 ? 'completed' : pipelineStage === 2 ? 'active' : ''}`}>2</div>
                  {/* Step 3: LLM Stage */}
                  <div className={`step neu-raised ${pipelineStage > 3 ? 'completed' : pipelineStage === 3 ? 'active' : ''}`}>3</div>
                  {/* Step 4: Validator */}
                  <div className={`step neu-raised ${pipelineStage > 4 ? 'completed' : pipelineStage === 4 ? 'active' : ''}`}>4</div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px', fontSize: '0.85rem', color: 'var(--text-color-muted)'}}>
                  <span>cAST</span>
                  <span>Prompt</span>
                  <span>LLM Agent</span>
                  <span>Validator</span>
                </div>
              </div>
            )}

            {/* Code Viewer: Shows when completed */}
            {pipelineStage === 5 && (
              <div className="pipeline-card neu-raised">
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <h3>Refactoring Results</h3>
                  <span style={{color: 'var(--accent-color)', fontWeight: 'bold', fontSize: '0.9rem'}}>100% Passed Validation</span>
                </div>
                <div 
                  className="neu-inset" 
                  style={{ 
                    marginTop: '24px', 
                    padding: '24px', 
                    fontFamily: 'monospace', 
                    fontSize: '0.9rem',
                    color: 'var(--text-color)',
                    maxHeight: '300px',
                    overflowY: 'auto',
                    whiteSpace: 'pre-wrap'
                  }}
                >
{`// Refactored Output
import React from 'react';

export const EnhancedComponent = () => {
  // Optimized execution payload
  const [data, setData] = useState(null);
  
  useEffect(() => {
    fetch('/api/v1/optimized')
      .then(res => res.json())
      .then(setData);
  }, []);

  return (
    <div>
      {data ? <RenderData payload={data} /> : <LoadingSpinner />}
    </div>
  );
};
`}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Configuration */}
          <div className="config-card neu-raised">
            <h3>Configuration</h3>
            
            <div className="config-group" style={{ marginTop: '16px' }}>
              <div className="config-header">
                <span className="config-label">Model Selection</span>
              </div>
              <select 
                className="neu-input" 
                value={model} 
                onChange={e => setModel(e.target.value)}
                style={{ appearance: 'none', cursor: 'pointer' }}
              >
                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                <option value="gpt-4o">GPT-4o</option>
              </select>
            </div>

            <div className="config-group" style={{ marginTop: '16px' }}>
              <div className="config-header">
                <span className="config-label">In-Place Refactoring</span>
                <div 
                  className={`toggle-switch neu-inset ${inPlace ? 'active' : ''}`}
                  onClick={() => setInPlace(!inPlace)}
                >
                  <div className="knob"></div>
                </div>
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-color-muted)' }}>
                Overwrite original files instead of output directory
              </p>
            </div>

            <div className="config-group" style={{ marginTop: '16px' }}>
              <div className="config-header">
                <span className="config-label">Batch Size: {batchSize}</span>
              </div>
              <input 
                type="range" 
                min="1" max="10" 
                value={batchSize} 
                onChange={(e) => setBatchSize(Number(e.target.value))} 
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-color-muted)'}}>
                <span>1</span>
                <span>10</span>
              </div>
            </div>

            <div className="config-group" style={{ marginTop: '16px' }}>
              <div className="config-header">
                <span className="config-label">API Throttling Delay: {delay}s</span>
              </div>
              <input 
                type="range" 
                min="0" max="60" step="5"
                value={delay} 
                onChange={(e) => setDelay(Number(e.target.value))} 
              />
            </div>

            <div className="action-area">
              <button 
                className="neu-button primary run-btn"
                onClick={handleRunRefactor}
                disabled={pipelineStage > 0 && pipelineStage < 5}
              >
                {pipelineStage > 0 && pipelineStage < 5 ? 'Processing...' : pipelineStage === 5 ? 'Run Again' : 'Run Pipeline'}
              </button>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
