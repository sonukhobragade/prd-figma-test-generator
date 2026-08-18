import { useState, useEffect } from 'react';
import { RefreshCw, Database, Code2, AlertCircle, Loader2, FolderCode, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface CodebaseStatus {
  enabled: boolean;
  health: string;
  collection?: string;
  documents?: number;
  codebase_path?: string;
  file_count?: number;
  chunk_count?: number;
  last_synced?: string;
  file_types?: Record<string, number>;
  message?: string;
}

export function CodebaseRAGStatus() {
  const [status, setStatus] = useState<CodebaseStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/rag/codebase/status');
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      setStatus({
        enabled: false,
        health: 'error',
        message: 'Failed to fetch status',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSync = async (force: boolean = false) => {
    setSyncing(true);
    setSyncResult(null);

    try {
      const formData = new FormData();
      formData.append('force', force.toString());

      const response = await fetch('/api/rag/codebase/sync', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.success) {
        setSyncResult(`${data.status === 'completed' ? 'Synced' : 'Skipped'}: ${data.message}`);
        fetchStatus();
      } else {
        setSyncResult(`Error: ${data.detail || data.message}`);
      }
    } catch (error) {
      setSyncResult(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setSyncing(false);
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr || dateStr === 'Never') return 'Never';
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  const getStatusInfo = () => {
    if (!status) return { color: 'bg-gray-400', glow: '', label: 'Unknown' };
    if (status.health === 'healthy') return {
      color: 'bg-emerald-500',
      glow: 'shadow-[0_0_8px_rgba(16,185,129,0.6)]',
      label: 'Connected'
    };
    if (status.health === 'offline') return {
      color: 'bg-amber-500',
      glow: 'shadow-[0_0_8px_rgba(245,158,11,0.6)]',
      label: 'Offline'
    };
    return {
      color: 'bg-red-500',
      glow: 'shadow-[0_0_8px_rgba(239,68,68,0.6)]',
      label: 'Error'
    };
  };

  const statusInfo = getStatusInfo();

  if (loading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-white border border-slate-200 p-4 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)]">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-rose-100 to-rose-50 flex items-center justify-center border border-rose-200">
              <Loader2 className="h-5 w-5 text-rose-600 animate-spin" />
            </div>
          </div>
          <div className="flex-1">
            <div className="h-4 w-36 bg-slate-200 rounded animate-pulse" />
            <div className="h-3 w-28 bg-slate-100 rounded mt-2 animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`
        relative overflow-hidden rounded-2xl
        bg-white
        border border-slate-200
        shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)]
        hover:shadow-[0_8px_30px_-4px_rgba(0,0,0,0.15)]
        hover:border-slate-300
        transition-all duration-300 ease-out
      `}
    >
      {/* Subtle gradient accent at top */}
      <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-primary to-transparent" />

      {/* Header - Clickable */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer group"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          {/* Icon with red/primary gradient background */}
          <div className="relative">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-rose-100 to-rose-50 flex items-center justify-center shadow-sm border border-rose-200">
              <Code2 className="h-5 w-5 text-rose-600" strokeWidth={2.5} />
            </div>
            {/* Sparkle accent */}
            <Sparkles className="absolute -top-1 -right-1 h-3 w-3 text-rose-500" />
          </div>

          {/* Title and Status */}
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-800 tracking-tight">
                Codebase Knowledge
              </span>
              {/* Status indicator with glow */}
              <div className="flex items-center gap-1.5">
                <span className={`
                  w-2 h-2 rounded-full ${statusInfo.color} ${statusInfo.glow}
                  animate-pulse
                `} />
                <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
                  {statusInfo.label}
                </span>
              </div>
            </div>

            {/* Stats row */}
            {status?.enabled && (
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-xs text-slate-500">
                  <span className="font-semibold text-slate-700">{status.documents?.toLocaleString()}</span>
                  {' '}chunks
                </span>
                <span className="w-1 h-1 rounded-full bg-slate-300" />
                <span className="text-xs text-slate-500">
                  <span className="font-semibold text-slate-700">{status.file_count?.toLocaleString()}</span>
                  {' '}files
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Right side actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600"
            onClick={(e) => {
              e.stopPropagation();
              setLoading(true);
              fetchStatus();
            }}
            title="Refresh status"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          <div className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 group-hover:text-slate-600 transition-colors">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-slate-100 pt-4 animate-in slide-in-from-top-2 duration-200">
          {status?.enabled ? (
            <>
              {/* Status Details Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-50/80 border border-slate-100">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                    <FolderCode className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Path</p>
                    <p className="text-xs text-slate-700 font-medium truncate" title={status.codebase_path}>
                      {status.codebase_path?.split('/').slice(-2).join('/')}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-50/80 border border-slate-100">
                  <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
                    <Database className="h-4 w-4 text-violet-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Collection</p>
                    <p className="text-xs text-slate-700 font-medium truncate">{status.collection}</p>
                  </div>
                </div>
              </div>

              {/* File Types */}
              {status.file_types && Object.keys(status.file_types).length > 0 && (
                <div className="space-y-2">
                  <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">File Types</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(status.file_types)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 6)
                      .map(([type, count]) => (
                        <span
                          key={type}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200/60 rounded-lg text-[11px] text-slate-600 font-medium"
                        >
                          <span className="text-slate-400">{type}</span>
                          <span className="text-primary font-semibold">{count}</span>
                        </span>
                      ))}
                  </div>
                </div>
              )}

              {/* Last Synced */}
              <div className="flex items-center justify-between text-xs text-slate-500 py-2 border-t border-slate-100">
                <span>Last synchronized</span>
                <span className="font-medium text-slate-600">{formatDate(status.last_synced || 'Never')}</span>
              </div>

              {/* Sync Buttons */}
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 h-9 text-xs font-medium rounded-xl border-slate-200 hover:bg-slate-50 hover:border-slate-300"
                  onClick={() => handleSync(false)}
                  disabled={syncing}
                >
                  {syncing ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 mr-2" />
                      Sync Codebase
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-9 text-xs px-3 font-medium rounded-xl border-slate-200 hover:bg-slate-50 hover:border-slate-300"
                  onClick={() => handleSync(true)}
                  disabled={syncing}
                  title="Force re-index all files"
                >
                  Force
                </Button>
              </div>

              {/* Sync Result */}
              {syncResult && (
                <div className={`
                  text-xs p-3 rounded-xl font-medium
                  ${syncResult.startsWith('Error')
                    ? 'bg-red-50 text-red-600 border border-red-100'
                    : 'bg-emerald-50 text-emerald-600 border border-emerald-100'
                  }
                `}>
                  {syncResult}
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center gap-3 p-3 rounded-xl bg-amber-50 border border-amber-100">
              <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0" />
              <span className="text-sm text-amber-700">{status?.message || 'Codebase RAG not available'}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
