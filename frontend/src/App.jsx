import { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';

// ─── Constants ────────────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8000/api/v1';
const WS_BASE  = 'ws://localhost:8000/api/v1/ws';

const STAGE_META = [
  { label: 'cAST',          desc: 'Parsing source into structured chunks' },
  { label: 'Prompt Builder', desc: 'Building LLM prompts from chunks' },
  { label: 'LLM Agent',     desc: 'Calling Gemini — refactoring code' },
  { label: 'Validator',     desc: 'Verifying syntax, AST & functional parity' },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function buildDiff(original, refactored) {
  if (!original || !refactored) return [];
  const origLines = original.split('\n');
  const refLines  = refactored.split('\n');
  const maxLen = Math.max(origLines.length, refLines.length);
  const rows = [];
  for (let i = 0; i < maxLen; i++) {
    const o = origLines[i] ?? '';
    const r = refLines[i] ?? '';
    rows.push({ line: i + 1, original: o, refactored: r, changed: o !== r });
  }
  return rows;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ValidationBadge({ report }) {
  if (!report || Object.keys(report).length === 0) return null;
  const passed = report.severity === 'pass';
  const passRate = report.pass_rate != null
    ? `${Math.round(report.pass_rate * 100)}%`
    : '—';
  return (
    <div className={`validation-badge ${passed ? 'pass' : 'fail'}`}>
      <span className="badge-icon">{passed ? '✓' : '✗'}</span>
      <span>{passed ? 'Validation Passed' : 'Validation Failed'}</span>
      <span className="badge-rate">{passRate}</span>
    </div>
  );
}

function ValidationChecks({ report }) {
  if (!report || !report.checks) return null;
  return (
    <div className="validation-checks">
      {Object.entries(report.checks).map(([name, info]) => {
        let passed = true;
        let message = '';
        if (Array.isArray(info) && info.length >= 2) {
          [passed, message] = info;
        } else if (typeof info === 'object' && info !== null) {
          passed  = info.passed ?? true;
          message = info.message ?? '';
        }
        return (
          <div key={name} className={`check-row ${passed ? 'pass' : 'fail'}`}>
            <span className="check-icon">{passed ? '✓' : '✗'}</span>
            <span className="check-name">{name}</span>
            {message && <span className="check-msg">{message}</span>}
          </div>
        );
      })}
    </div>
  );
}

function DiffViewer({ originalCode, refactoredCode }) {
  const [mode, setMode] = useState('split'); // 'split' | 'unified'
  const rows = buildDiff(originalCode, refactoredCode);
  const changedCount = rows.filter(r => r.changed).length;

  if (!refactoredCode) return null;

  return (
    <div className="diff-viewer">
      <div className="diff-toolbar">
        <div className="diff-stats">
          <span className="stat changed">{changedCount} lines changed</span>
          <span className="stat total">{rows.length} total</span>
        </div>
        <div className="diff-mode-toggle">
          <button
            className={`mode-btn ${mode === 'split' ? 'active' : ''}`}
            onClick={() => setMode('split')}
          >Split</button>
          <button
            className={`mode-btn ${mode === 'unified' ? 'active' : ''}`}
            onClick={() => setMode('unified')}
          >Unified</button>
        </div>
      </div>

      <div className={`diff-body ${mode}`}>
        {mode === 'split' ? (
          <div className="split-panes">
            <div className="pane">
              <div className="pane-header">Original</div>
              <div className="pane-content neu-inset">
                {rows.map(r => (
                  <div key={r.line} className={`diff-line ${r.changed ? 'changed' : ''}`}>
                    <span className="line-no">{r.line}</span>
                    <span className="line-text">{r.original || '\u00a0'}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="pane">
              <div className="pane-header">Refactored</div>
              <div className="pane-content neu-inset">
                {rows.map(r => (
                  <div key={r.line} className={`diff-line ${r.changed ? 'changed refactored' : ''}`}>
                    <span className="line-no">{r.line}</span>
                    <span className="line-text">{r.refactored || '\u00a0'}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="unified-pane neu-inset">
            {rows.map(r => (
              r.changed ? (
                <div key={`u-${r.line}`}>
                  <div className="diff-line removed">
                    <span className="line-no">{r.line}</span>
                    <span className="diff-marker">-</span>
                    <span className="line-text">{r.original || '\u00a0'}</span>
                  </div>
                  <div className="diff-line added">
                    <span className="line-no">{r.line}</span>
                    <span className="diff-marker">+</span>
                    <span className="line-text">{r.refactored || '\u00a0'}</span>
                  </div>
                </div>
              ) : (
                <div key={`u-${r.line}`} className="diff-line">
                  <span className="line-no">{r.line}</span>
                  <span className="diff-marker"> </span>
                  <span className="line-text">{r.original || '\u00a0'}</span>
                </div>
              )
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function JobHistoryItem({ job, onSelect, isActive }) {
  const statusColor = {
    completed: 'var(--accent-color)',
    failed: '#e53e3e',
    cancelled: '#a0aec0',
    running: '#ed8936',
    queued: 'var(--text-color-muted)',
  }[job.status] ?? 'var(--text-color-muted)';

  return (
    <div
      className={`history-item neu-raised ${isActive ? 'active' : ''}`}
      onClick={() => onSelect(job)}
    >
      <div className="history-filename">{job.filename}</div>
      <div className="history-meta">
        <span style={{ color: statusColor }}>{job.status}</span>
        <span>{new Date(job.created_at).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}

function MultiFileTabs({ files, originalCode }) {
  const [active, setActive] = useState(0);
  const cur = files[active];
  return (
    <div className="multi-file-tabs">
      <div className="tab-bar">
        {files.map((f, i) => {
          const rep = f.validation_report ?? {};
          const passed = rep.severity === 'pass';
          return (
            <button
              key={i}
              className={`tab-btn ${active === i ? 'active' : ''}`}
              onClick={() => setActive(i)}
            >
              <span className={`tab-dot ${passed ? 'pass' : 'fail'}`}></span>
              {f.filename}
            </button>
          );
        })}
      </div>
      <div className="tab-content">
        <ValidationChecks report={cur.validation_report} />
        {cur.refactored_code && (
          <DiffViewer 
            originalCode={cur.original_code || originalCode} 
            refactoredCode={cur.refactored_code} 
          />
        )}
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
function App() {
  // Config
  const [inPlace, setInPlace]           = useState(false);
  const [batchSize, setBatchSize]       = useState(3);
  const [delay, setDelay]               = useState(2);
  const [model, setModel]               = useState('gemma-3-1b');
  const [noFunctional, setNoFunctional] = useState(false);
  const [uploadMode, setUploadMode]     = useState('file'); // 'file' | 'folder' | 'zip'

  // File
  const [selectedFiles, setSelectedFiles]   = useState([]);   // always an array
  const [originalCode, setOriginalCode]     = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDragging, setIsDragging]         = useState(false);

  // Job state
  const [jobId, setJobId]       = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // full job object
  const [results, setResults]   = useState(null);
  const [error, setError]       = useState(null);

  // Job history
  const [jobs, setJobs]         = useState([]);
  const [activeView, setActiveView] = useState('dashboard'); // 'dashboard' | 'history'

  // WebSocket ref
  const wsRef = useRef(null);

  // ── Derived state
  const stage          = jobStatus?.stage ?? 0;
  const pipelineState  = jobStatus?.status ?? 'idle';
  const isRunning      = ['queued', 'running'].includes(pipelineState);
  const selectedFile   = selectedFiles[0] ?? null;   // back-compat alias
  const totalFileCount = selectedFiles.length;

  // ── Fetch job history ──────────────────────────────────────────────────────
  const refreshHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/jobs`);
      if (res.ok) setJobs(await res.json());
    } catch (_) {}
  }, []);

  useEffect(() => { refreshHistory(); }, [refreshHistory]);

  // ── WebSocket subscription with exponential backoff ─────────────────────────
  const wsRetriesRef = useRef(0);
  const wsTimerRef   = useRef(null);
  const MAX_WS_RETRIES = 5;

  const connectWS = useCallback((jid) => {
    // Clear any pending reconnection timer
    if (wsTimerRef.current) {
      clearTimeout(wsTimerRef.current);
      wsTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(`${WS_BASE}/${jid}`);
    wsRef.current = ws;

    ws.onopen = () => {
      wsRetriesRef.current = 0;     // Reset backoff on successful connect
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.error) return;
      setJobStatus(data);

      // When job finishes (including cancellation), fetch full results
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        if (data.status !== 'cancelled') fetchResults(jid);
        refreshHistory();
      }
    };

    ws.onclose = (event) => {
      // Don't reconnect if we closed intentionally or job is done
      const currentStatus = _jobs?.status;
      if (event.code === 1000 || wsRetriesRef.current >= MAX_WS_RETRIES) return;

      // Exponential backoff: 1s, 2s, 4s, 8s, 16s
      const delay = Math.min(1000 * Math.pow(2, wsRetriesRef.current), 16000);
      wsRetriesRef.current += 1;
      console.log(`WebSocket reconnecting in ${delay}ms (attempt ${wsRetriesRef.current}/${MAX_WS_RETRIES})`);
      wsTimerRef.current = setTimeout(() => connectWS(jid), delay);
    };

    ws.onerror = () => {
      // onclose will fire after this and handle reconnection
    };
  }, [refreshHistory]);

  // ── Polling fallback ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!jobId || !isRunning) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          setJobStatus(prev => ({ ...prev, ...data }));
          if (['completed', 'failed', 'cancelled'].includes(data.status)) {
            clearInterval(interval);
            if (data.status !== 'cancelled') fetchResults(jobId);
            refreshHistory();
          }
        }
      } catch (_) {}
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, isRunning, refreshHistory]);

  // ── Fetch results ──────────────────────────────────────────────────────────
  const fetchResults = async (jid) => {
    try {
      const res = await fetch(`${API_BASE}/results/${jid}`);
      if (res.ok) setResults(await res.json());
    } catch (_) {}
  };

  // ── Load a historical job ──────────────────────────────────────────────────
  const loadHistoryJob = async (job) => {
    setJobId(job.job_id);
    setJobStatus(job);
    setError(null);
    setActiveView('dashboard');
    if (job.status === 'completed' || job.status === 'failed') {
      fetchResults(job.job_id);
    } else {
      connectWS(job.job_id);
    }
  };

  // ── File handling ──────────────────────────────────────────────────────────
  const processFiles = (fileList) => {
    const arr = Array.from(fileList);
    const valid = uploadMode === 'zip'
      ? arr.filter(f => f.name.endsWith('.zip'))
      : arr.filter(f => f.name.endsWith('.py'));
    if (valid.length === 0) {
      setError(uploadMode === 'zip' ? 'Please select a .zip archive.' : 'No .py files found.');
      return;
    }
    setSelectedFiles(valid);
    setError(null);
    setResults(null);
    setJobStatus(null);
    // Read first file for diff preview
    const reader = new FileReader();
    reader.onload = (e) => setOriginalCode(e.target.result);
    reader.readAsText(valid[0]);
  };

  const killJob = async () => {
    if (!jobId) return;
    try {
      await axios.post(`${API_BASE}/jobs/${jobId}/cancel`);
    } catch (err) {
      console.error("Kill failed:", err);
    }
  };

  const cleanupAll = async () => {
    if (!window.confirm("This will kill all running jobs and clear history. Continue?")) return;
    try {
      await axios.delete(`${API_BASE}/jobs/cleanup`);
      setHistory([]);
      setJobId(null);
      setJobStatus(null);
    } catch (err) {
      console.error("Cleanup failed:", err);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files?.length) processFiles(e.target.files);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length) processFiles(e.dataTransfer.files);
  };

  // ── Submit job ─────────────────────────────────────────────────────────────
  const handleRunRefactor = async () => {
    if (selectedFiles.length === 0) { setError('Please select file(s) first.'); return; }

    setError(null);
    setResults(null);
    setUploadProgress(0);

    const formData = new FormData();
    selectedFiles.forEach(f => formData.append('files', f));
    formData.append('model', model);
    formData.append('batch_size', batchSize);
    formData.append('delay', delay);
    formData.append('in_place', inPlace);
    formData.append('no_functional', noFunctional);

    try {
      // XHR for upload progress
      const jid = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100));
        };
        xhr.onload = () => {
          if (xhr.status === 202) {
            resolve(JSON.parse(xhr.responseText).job_id);
          } else {
            reject(new Error(`Server error ${xhr.status}: ${xhr.responseText}`));
          }
        };
        xhr.onerror = () => reject(new Error('Network error during upload.'));
        xhr.open('POST', `${API_BASE}/refactor`);
        xhr.send(formData);
      });

      setJobId(jid);
      setJobStatus({ job_id: jid, stage: 0, status: 'queued', stage_label: 'idle' });
      connectWS(jid);
      refreshHistory();
    } catch (err) {
      setError(err.message);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
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
          <div
            className={`nav-item ${activeView === 'dashboard' ? 'active neu-inset' : ''}`}
            onClick={() => setActiveView('dashboard')}
          >Dashboard</div>
          <div
            className={`nav-item ${activeView === 'history' ? 'active neu-inset' : ''}`}
            onClick={() => { setActiveView('history'); refreshHistory(); }}
          >
            History
            {jobs.length > 0 && <span className="badge">{jobs.length}</span>}
          </div>
          <div className="nav-item">Settings</div>
        </nav>

        {/* Connection status */}
        <div className="conn-status">
          <div className={`conn-dot ${wsRef.current?.readyState === 1 ? 'connected' : 'disconnected'}`}></div>
          <span>{wsRef.current?.readyState === 1 ? 'Live' : 'Idle'}</span>
        </div>
      </aside>

      {/* Main Workspace */}
      <main className="main-content">
        <header className="header">
          <div>
            <h2>{activeView === 'history' ? 'Job History' : 'Refactoring Dashboard'}</h2>
            <p style={{ color: 'var(--text-color-muted)', marginTop: 4 }}>
              {activeView === 'history'
                ? 'Select a past job to view its results.'
                : 'Upload a Python file to start the AI refactoring pipeline.'}
            </p>
          </div>
          <div className="user-profile neu-raised">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
          </div>
        </header>

        {/* ── History View ───────────────────────────────────────────────── */}
        {activeView === 'history' && (
          <div className="history-list">
            <div className="history-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0 }}>Recent Jobs</h3>
              <button 
                className="mode-chip neu-raised" 
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                onClick={cleanupAll}
              >
                🗑 Clear All
              </button>
            </div>
            {jobs.length === 0 ? (
              <div className="empty-state neu-raised">
                <p>No jobs yet. Run your first refactoring from the Dashboard.</p>
              </div>
            ) : (
              jobs.map(job => (
                <JobHistoryItem
                  key={job.job_id}
                  job={job}
                  onSelect={loadHistoryJob}
                  isActive={job.job_id === jobId}
                />
              ))
            )}
          </div>
        )}

        {/* ── Dashboard View ─────────────────────────────────────────────── */}
        {activeView === 'dashboard' && (
          <div className="dashboard-grid">
            {/* Left Column */}
            <div className="left-col">
              {/* Upload Zone */}
              <div className="upload-card neu-raised">
                <div className="upload-mode-switcher">
                  <h3>Source Code</h3>
                  <div className="mode-toggle-group">
                    {['file', 'folder', 'zip'].map(m => (
                      <button
                        key={m}
                        className={`mode-chip ${uploadMode === m ? 'active' : ''}`}
                        onClick={() => { setUploadMode(m); setSelectedFiles([]); setOriginalCode(null); }}
                        disabled={isRunning}
                      >
                        {m === 'file' ? '📄 File' : m === 'folder' ? '📁 Folder' : '🗜 ZIP'}
                      </button>
                    ))}
                  </div>
                </div>

                <div
                  className={`drop-zone neu-inset ${isDragging ? 'dragging' : ''}`}
                  onClick={() => document.getElementById('fileInput').click()}
                  onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                >
                  <input
                    id="fileInput"
                    type="file"
                    accept={uploadMode === 'zip' ? '.zip' : '.py'}
                    multiple={uploadMode === 'file' || uploadMode === 'zip'}
                    {...(uploadMode === 'folder' ? { webkitdirectory: '', directory: '' } : {})}
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                  />
                  <div className="drop-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                      <polyline points="17 8 12 3 7 8"></polyline>
                      <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                  </div>
                  {totalFileCount > 0 ? (
                    <div>
                      <h4>{totalFileCount === 1 ? selectedFile.name : `${totalFileCount} files selected`}</h4>
                      <p style={{ fontSize: '0.8rem', marginTop: 4 }}>
                        {totalFileCount === 1
                          ? `${formatBytes(selectedFile.size)} · Click to change`
                          : `Total: ${formatBytes(selectedFiles.reduce((s, f) => s + f.size, 0))} · Click to change`}
                      </p>
                    </div>
                  ) : (
                    <div>
                      <h4>{uploadMode === 'folder' ? 'Click to select a folder' : uploadMode === 'zip' ? 'Drop a .zip archive here' : 'Drag & Drop .py files here'}</h4>
                      <p>or click to browse</p>
                    </div>
                  )}
                  <button className="neu-button" style={{ marginTop: 12 }}>
                    {totalFileCount > 0 ? 'Change' : uploadMode === 'folder' ? 'Select Folder' : uploadMode === 'zip' ? 'Select ZIP' : 'Select Files'}
                  </button>
                </div>

                {/* Upload progress bar */}
                {uploadProgress > 0 && uploadProgress < 100 && (
                  <div className="upload-progress">
                    <div className="progress-track neu-inset">
                      <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
                    </div>
                    <span>{uploadProgress}%</span>
                  </div>
                )}
              </div>

              {/* Error banner */}
              {error && (
                <div className="alert error-alert neu-raised">
                  <span className="alert-icon">⚠</span>
                  <span>{error}</span>
                </div>
              )}

              {/* Pipeline tracker */}
              {(stage > 0 || isRunning) && (
                <div className="pipeline-card neu-raised">
                  <div className="pipeline-header">
                    <h3>Pipeline Status</h3>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      {isRunning && (
                        <button 
                          className="kill-btn neu-raised" 
                          onClick={killJob}
                          title="Terminate running job"
                        >
                          ✕ Stop
                        </button>
                      )}
                      <span className={`status-chip status-${pipelineState}`}>
                        {pipelineState}
                      </span>
                    </div>
                  </div>

                  {/* Job ID badge */}
                  {jobId && (
                    <div className="job-id-badge neu-inset">
                      <span>Job:</span>
                      <code>{jobId.slice(0, 18)}…</code>
                    </div>
                  )}

                  <div className="steps">
                    {STAGE_META.map((s, i) => {
                      const stageNum = i + 1;
                      const cls = stage > stageNum ? 'completed'
                                : stage === stageNum ? 'active'
                                : '';
                      return (
                        <div key={s.label} className={`step-container`}>
                          <div className={`step neu-raised ${cls}`} title={s.desc}>
                            {stage > stageNum ? '✓' : stageNum}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="step-labels">
                    {STAGE_META.map((s, i) => {
                      const stageNum = i + 1;
                      const startTime = jobStatus?.stage_times?.[stageNum.toString()];
                      const endTime   = jobStatus?.stage_times?.[(stageNum + 1).toString()];
                      let duration = null;
                      if (startTime && endTime) {
                        duration = Math.max(0, Math.round((new Date(endTime) - new Date(startTime)) / 1000));
                      }
                      
                      return (
                        <div key={s.label} className="step-label-item">
                          <div className="label-text">{s.label}</div>
                          {duration !== null && (
                            <div className="duration-tag">{duration}s</div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Active stage description */}
                  {stage > 0 && stage <= 4 && (
                    <div className="stage-desc neu-inset">
                      <div className="spinner"></div>
                      {STAGE_META[stage - 1].desc}…
                    </div>
                  )}

                  {/* ── Pipeline Runtime Breakdown ─────────────────────── */}
                  {(() => {
                    const times = jobStatus?.stage_times ?? {};
                    const rows = STAGE_META.map((s, i) => {
                      const stageNum  = i + 1;
                      const start     = times[stageNum.toString()];
                      const end       = times[(stageNum + 1).toString()];
                      const completed = stage > stageNum;
                      const active    = stage === stageNum;
                      const dur = (start && end)
                        ? Math.round((new Date(end) - new Date(start)) / 1000)
                        : null;
                      return { label: s.label, dur, completed, active };
                    });

                    // Total: from stage 1 start to stage 5 (done) timestamp
                    const totalStart = times['1'];
                    const totalEnd   = times['5'];
                    const totalDur   = (totalStart && totalEnd)
                      ? Math.round((new Date(totalEnd) - new Date(totalStart)) / 1000)
                      : null;

                    const hasAnyData = rows.some(r => r.dur !== null || r.active || r.completed);
                    if (!hasAnyData) return null;

                    return (
                      <div className="runtime-panel neu-inset">
                        <div className="runtime-title">⏱ Pipeline Runtime</div>
                        <div className="runtime-rows">
                          {rows.map(r => (
                            <div key={r.label} className={`runtime-row ${r.completed ? 'done' : r.active ? 'active' : 'pending'}`}>
                              <div className="runtime-stage-dot" />
                              <span className="runtime-label">{r.label}</span>
                              <span className="runtime-val">
                                {r.dur !== null
                                  ? `${r.dur}s`
                                  : r.active ? <span className="runtime-running">running…</span>
                                  : '—'}
                              </span>
                            </div>
                          ))}
                          <div className="runtime-total">
                            <span>Total</span>
                            <span>{totalDur !== null ? `${totalDur}s` : '—'}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Job-specific error */}
                  {jobStatus?.error && (
                    <div className="alert error-alert job-error neu-raised" style={{ marginTop: 16 }}>
                      <span className="alert-icon">✖</span>
                      <div className="error-content">
                        <strong>Pipeline Failed</strong>
                        <p>{jobStatus.error}</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Results */}
              {results && (
                <div className="results-card neu-raised">
                <div className="results-header">
                  <h3>Results — {results.filenames?.length > 1 ? `${results.filenames.length} files` : results.filename}</h3>
                </div>
                {/* Multi-file tabs */}
                {results.per_file_results?.length > 1 ? (
                  <MultiFileTabs files={results.per_file_results} originalCode={originalCode} />
                ) : (
                  <>
                    <ValidationBadge report={results.validation_report} />
                    <ValidationChecks report={results.validation_report} />
                    {results.refactored_code && (
                      <DiffViewer
                        originalCode={originalCode}
                        refactoredCode={results.refactored_code}
                      />
                    )}
                  </>
                )}

                {/* Raw output collapse */}
                {results.stdout && (
                  <details className="raw-output">
                    <summary>Pipeline Log</summary>
                    <pre className="neu-inset">{results.stdout}</pre>
                  </details>
                )}
                {results.stderr && (
                  <details className="raw-output">
                    <summary>Stderr</summary>
                    <pre className="neu-inset stderr">{results.stderr}</pre>
                  </details>
                )}
              </div>
            )}
          </div>

            {/* Right Column: Configuration */}
            <div className="config-card neu-raised">
              <h3>Configuration</h3>

              <div className="config-group" style={{ marginTop: 16 }}>
                <div className="config-header">
                  <span className="config-label">Model</span>
                </div>
                <select
                  className="neu-input"
                  value={model}
                  onChange={e => setModel(e.target.value)}
                  style={{ appearance: 'none', cursor: 'pointer' }}
                  disabled={isRunning}
                >
                  <option value="gemma-3-1b">Gemma 3 1B</option>
                  <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                  <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                </select>
              </div>

              <div className="config-group" style={{ marginTop: 16 }}>
                <div className="config-header">
                  <span className="config-label">In-Place Refactoring</span>
                  <div
                    className={`toggle-switch neu-inset ${inPlace ? 'active' : ''}`}
                    onClick={() => !isRunning && setInPlace(!inPlace)}
                  >
                    <div className="knob"></div>
                  </div>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-color-muted)' }}>
                  Overwrite original files instead of output directory
                </p>
              </div>

              <div className="config-group" style={{ marginTop: 16 }}>
                <div className="config-header">
                  <span className="config-label">Skip Functional Tests</span>
                  <div
                    className={`toggle-switch neu-inset ${noFunctional ? 'active' : ''}`}
                    onClick={() => !isRunning && setNoFunctional(!noFunctional)}
                  >
                    <div className="knob"></div>
                  </div>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-color-muted)' }}>
                  Skip behavioral validation (use for files with project-local imports)
                </p>
              </div>

              <div className="config-group" style={{ marginTop: 16 }}>
                <div className="config-header">
                  <span className="config-label">Batch Size: {batchSize}</span>
                </div>
                <input
                  type="range" min="1" max="10"
                  value={batchSize}
                  onChange={e => setBatchSize(Number(e.target.value))}
                  disabled={isRunning}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-color-muted)' }}>
                  <span>1</span><span>10</span>
                </div>
              </div>

              <div className="config-group" style={{ marginTop: 16 }}>
                <div className="config-header">
                  <span className="config-label">API Delay: {delay}s</span>
                </div>
                <input
                  type="range" min="0" max="60" step="5"
                  value={delay}
                  onChange={e => setDelay(Number(e.target.value))}
                  disabled={isRunning}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-color-muted)' }}>
                  <span>0s</span><span>60s</span>
                </div>
              </div>

              {/* API info */}
              <div className="api-info neu-inset">
                <div className="api-row">
                  <span>Backend</span>
                  <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
                    localhost:8000
                  </a>
                </div>
                <div className="api-row">
                  <span>Active Jobs</span>
                  <span>{jobs.filter(j => j.status === 'running').length}</span>
                </div>
                {jobId && (
                  <div className="api-row">
                    <span>Job ID</span>
                    <code style={{ fontSize: '0.7rem' }}>{jobId.slice(0, 12)}…</code>
                  </div>
                )}
              </div>

              <div className="action-area">
                <button
                  className="neu-button primary run-btn"
                  onClick={isRunning ? undefined : handleRunRefactor}
                  disabled={isRunning}
                >
                  {isRunning ? (
                    <><span className="spinner-sm"></span> Processing…</>
                  ) : results ? 'Run Again' : 'Run Pipeline'}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
