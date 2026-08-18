import { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, Database, Clock, AlertCircle, CheckCircle, ChevronDown, ChevronUp, Search, Settings, Plus, Minus, Edit3, BookOpen, Upload, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface ZKStatus {
  success: boolean;
  enabled: boolean;
  zk_live_config_count: number;
  zk_config_docs_count: number;
  last_sync?: string;
  message?: string;
}

interface ConfigChange {
  path: string;
  preview?: string;
  old_preview?: string;
  new_preview?: string;
}

interface ChangelogEntry {
  sync_time: string;
  total_configs: number;
  previous_count: number;
  summary?: {
    added: number;
    removed: number;
    modified: number;
    unchanged: number;
  };
  added?: ConfigChange[];
  removed?: ConfigChange[];
  modified?: ConfigChange[];
  paths_synced: string[];
  // Legacy fields
  new_configs?: number;
  config_paths?: string[];
}

interface SyncResult {
  success: boolean;
  message: string;
  configs_synced: number;
  previous_count: number;
  summary?: {
    added: number;
    removed: number;
    modified: number;
  };
  added?: ConfigChange[];
  removed?: ConfigChange[];
  modified?: ConfigChange[];
  sync_time: string;
}

interface ZKConfig {
  path: string;
  config_name: string;
  category: string;
  text: string;
  score?: number;
}

interface ZKConfigDoc {
  config_name: string;
  category: string;
  config_type: string;
  description: string;
  behavioral_impact: string;
  examples: { value: string; effect: string }[];
  implementation_ref: string;
  default_value: string;
  related_configs: string[];
}

interface DocsStatus {
  success: boolean;
  enabled: boolean;
  docs_count: number;
  last_updated?: string;
  source_file?: string;
  categories?: Record<string, string[]>;
}

export function ZKConfigPanel() {
  const [status, setStatus] = useState<ZKStatus | null>(null);
  const [changelog, setChangelog] = useState<ChangelogEntry[]>([]);
  const [configs, setConfigs] = useState<ZKConfig[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [expandedEntry, setExpandedEntry] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeView, setActiveView] = useState<'changelog' | 'changes' | 'configs' | 'docs'>('changelog');
  const [expandedConfigs, setExpandedConfigs] = useState<Set<string>>(new Set());
  const [fullConfigCache, setFullConfigCache] = useState<Record<string, string>>({});
  const [loadingConfigs, setLoadingConfigs] = useState<Set<string>>(new Set());

  // Config Documentation state
  const [docsStatus, setDocsStatus] = useState<DocsStatus | null>(null);
  const [configDocs, setConfigDocs] = useState<ZKConfigDoc[]>([]);
  const [isUploadingDocs, setIsUploadingDocs] = useState(false);
  const [docsSearchQuery, setDocsSearchQuery] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // New UI state for improved docs view
  const [selectedConfig, setSelectedConfig] = useState<ZKConfigDoc | null>(null);
  const [showAllCategories, setShowAllCategories] = useState(false);
  const [docsCurrentPage, setDocsCurrentPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const DOCS_PER_PAGE = 10;

  // Fetch full config data by path
  const fetchFullConfig = async (path: string): Promise<string | null> => {
    try {
      const response = await fetch(`/api/zk/configs?search=${encodeURIComponent(path)}&limit=1`);
      const data = await response.json();
      if (data.success && data.configs && data.configs.length > 0) {
        return data.configs[0].text || null;
      }
    } catch (err) {
      console.error('Failed to fetch full config:', err);
    }
    return null;
  };

  // Toggle config expansion and fetch full data if needed
  const toggleConfigExpand = async (key: string, path?: string) => {
    const isCurrentlyExpanded = expandedConfigs.has(key);

    setExpandedConfigs(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });

    // Fetch full config if expanding and not already cached
    if (!isCurrentlyExpanded && path && !fullConfigCache[path]) {
      setLoadingConfigs(prev => new Set(prev).add(key));
      const fullConfig = await fetchFullConfig(path);
      if (fullConfig) {
        setFullConfigCache(prev => ({ ...prev, [path]: fullConfig }));
      }
      setLoadingConfigs(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  // Fetch ZK status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/zk/status');
      const data = await response.json();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch ZK status:', err);
    }
  }, []);

  // Fetch changelog
  const fetchChangelog = useCallback(async () => {
    try {
      const response = await fetch('/api/zk/changelog?limit=20');
      const data = await response.json();
      if (data.success) {
        setChangelog(data.changelog || []);
      }
    } catch (err) {
      console.error('Failed to fetch changelog:', err);
    }
  }, []);

  // Fetch configs
  const fetchConfigs = useCallback(async (search?: string) => {
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      params.append('limit', '50');

      const response = await fetch(`/api/zk/configs?${params}`);
      const data = await response.json();
      if (data.success) {
        setConfigs(data.configs || []);
      }
    } catch (err) {
      console.error('Failed to fetch configs:', err);
    }
  }, []);

  // Fetch config docs status
  const fetchDocsStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/zk/docs/status');
      const data = await response.json();
      setDocsStatus(data);
    } catch (err) {
      console.error('Failed to fetch docs status:', err);
    }
  }, []);

  // Fetch all config docs
  const fetchConfigDocs = useCallback(async () => {
    try {
      const response = await fetch('/api/zk/docs/all');
      const data = await response.json();
      if (data.success) {
        setConfigDocs(data.docs || []);
      }
    } catch (err) {
      console.error('Failed to fetch config docs:', err);
    }
  }, []);

  // Search config docs
  const searchConfigDocs = useCallback(async (query: string) => {
    if (!query) {
      fetchConfigDocs();
      return;
    }
    try {
      const response = await fetch(`/api/zk/docs/search?q=${encodeURIComponent(query)}&limit=20`);
      const data = await response.json();
      if (data.success) {
        setConfigDocs(data.configs || []);
      }
    } catch (err) {
      console.error('Failed to search config docs:', err);
    }
  }, [fetchConfigDocs]);

  // Upload config docs
  const handleDocsUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploadingDocs(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/zk/docs/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      // Refresh docs data
      await Promise.all([fetchDocsStatus(), fetchConfigDocs()]);

      // Show success (could use a toast here)
      console.log('Docs uploaded:', data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploadingDocs(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      await Promise.all([fetchStatus(), fetchChangelog(), fetchConfigs(), fetchDocsStatus(), fetchConfigDocs()]);
      setIsLoading(false);
    };
    loadData();
  }, [fetchStatus, fetchChangelog, fetchConfigs, fetchDocsStatus, fetchConfigDocs]);

  // Search docs
  useEffect(() => {
    if (activeView !== 'docs') return;
    const timeoutId = setTimeout(() => {
      searchConfigDocs(docsSearchQuery);
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [docsSearchQuery, activeView, searchConfigDocs]);

  // Search configs
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (activeView === 'configs') {
        fetchConfigs(searchQuery);
      }
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [searchQuery, activeView, fetchConfigs]);

  // Sync ZK configs
  const handleSync = async () => {
    setIsSyncing(true);
    setError(null);
    setSyncResult(null);

    try {
      const response = await fetch('/api/zk/sync', {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Sync failed');
      }

      const data = await response.json();
      setSyncResult(data);

      // Refresh data
      await Promise.all([fetchStatus(), fetchChangelog(), fetchConfigs()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync');
    } finally {
      setIsSyncing(false);
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  // Format relative time
  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  // Format config data - try to parse as JSON and pretty print
  const formatConfigData = (text: string): string => {
    if (!text) return '';

    // Remove the prefix if present (e.g., "ZK Config: ... Data:")
    let data = text;
    const dataIndex = text.indexOf('Data:');
    if (dataIndex !== -1) {
      data = text.substring(dataIndex + 5).trim();
    }

    // Try to parse and format as JSON
    try {
      // Find JSON object or array in the text
      const jsonMatch = data.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[1]);
        return JSON.stringify(parsed, null, 2);
      }
    } catch {
      // JSON parsing failed - try to format manually for readability
      // Add line breaks after common JSON patterns
      try {
        return data
          .replace(/,\s*"/g, ',\n  "')
          .replace(/\{\s*"/g, '{\n  "')
          .replace(/"\s*\}/g, '"\n}')
          .replace(/\[\s*\{/g, '[\n  {')
          .replace(/\}\s*\]/g, '}\n]')
          .replace(/\}\s*,\s*\{/g, '},\n  {');
      } catch {
        // If manual formatting fails, return as-is
      }
    }

    // Return as-is if nothing worked
    return data;
  };

  // Compute diff between old and new JSON configs - handles nested objects and arrays
  const computeDiff = (oldText: string, newText: string): { added: string[], removed: string[], changed: { key: string, old: string, new: string }[] } => {
    const diff = { added: [] as string[], removed: [] as string[], changed: [] as { key: string, old: string, new: string }[] };

    try {
      const oldData = formatConfigData(oldText);
      const newData = formatConfigData(newText);

      const oldJson = JSON.parse(oldData);
      const newJson = JSON.parse(newData);

      // Recursively find differences
      const findDiffs = (oldVal: unknown, newVal: unknown, path: string) => {
        // Both are objects (not arrays)
        if (oldVal && newVal && typeof oldVal === 'object' && typeof newVal === 'object' && !Array.isArray(oldVal) && !Array.isArray(newVal)) {
          const oldObj = oldVal as Record<string, unknown>;
          const newObj = newVal as Record<string, unknown>;
          const allKeys = new Set([...Object.keys(oldObj), ...Object.keys(newObj)]);

          for (const key of allKeys) {
            const newPath = path ? `${path}.${key}` : key;
            if (!(key in oldObj)) {
              // Key added
              const val = JSON.stringify(newObj[key]);
              diff.added.push(`${newPath}: ${val.length > 50 ? val.slice(0, 50) + '...' : val}`);
            } else if (!(key in newObj)) {
              // Key removed
              const val = JSON.stringify(oldObj[key]);
              diff.removed.push(`${newPath}: ${val.length > 50 ? val.slice(0, 50) + '...' : val}`);
            } else {
              // Key exists in both - recurse
              findDiffs(oldObj[key], newObj[key], newPath);
            }
          }
        }
        // Both are arrays
        else if (Array.isArray(oldVal) && Array.isArray(newVal)) {
          const maxLen = Math.max(oldVal.length, newVal.length);
          for (let i = 0; i < maxLen; i++) {
            const newPath = `${path}[${i}]`;
            if (i >= oldVal.length) {
              const val = JSON.stringify(newVal[i]);
              diff.added.push(`${newPath}: ${val.length > 50 ? val.slice(0, 50) + '...' : val}`);
            } else if (i >= newVal.length) {
              const val = JSON.stringify(oldVal[i]);
              diff.removed.push(`${newPath}: ${val.length > 50 ? val.slice(0, 50) + '...' : val}`);
            } else {
              findDiffs(oldVal[i], newVal[i], newPath);
            }
          }
        }
        // Primitive values or type mismatch
        else if (JSON.stringify(oldVal) !== JSON.stringify(newVal)) {
          const oldStr = JSON.stringify(oldVal);
          const newStr = JSON.stringify(newVal);
          diff.changed.push({
            key: path,
            old: oldStr.length > 30 ? oldStr.slice(0, 30) + '...' : oldStr,
            new: newStr.length > 30 ? newStr.slice(0, 30) + '...' : newStr
          });
        }
      };

      findDiffs(oldJson, newJson, '');
    } catch {
      // If parsing fails, return empty diff
    }

    return diff;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background px-6 py-4">
        <div className="max-w-full mx-auto">
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <span className="ml-3 text-muted-foreground">Loading ZooKeeper config...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-6 py-4">
      <div className="max-w-full mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
              <Settings className="h-6 w-6" style={{ color: "hsl(var(--primary))" }} />
              ZooKeeper Config
            </h2>
            <p className="text-muted-foreground mt-1">
              Sync and manage live ZooKeeper configurations
            </p>
          </div>
          <Button
            onClick={handleSync}
            disabled={isSyncing}
            className="gap-2"
            style={{ backgroundColor: "hsl(var(--primary))" }}
          >
            <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
            {isSyncing ? 'Syncing...' : 'Sync Now'}
          </Button>
        </div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Live Configs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5" style={{ color: "hsl(var(--primary))" }} />
                <span className="text-2xl font-bold">{status?.zk_live_config_count || 0}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Doc Configs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5 text-blue-500" />
                <span className="text-2xl font-bold">{status?.zk_config_docs_count || 0}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                {status?.enabled ? (
                  <>
                    <CheckCircle className="h-5 w-5 text-green-500" />
                    <span className="text-green-600 font-medium">Connected</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-5 w-5 text-yellow-500" />
                    <span className="text-yellow-600 font-medium">Offline</span>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sync Result */}
        {syncResult && (
          <Card className="border-green-200 bg-green-50">
            <CardContent className="pt-4">
              <div className="flex items-start gap-3">
                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-green-800">{syncResult.message}</p>

                  {/* Summary badges */}
                  {syncResult.summary && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {syncResult.summary.added > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded text-sm font-medium">
                          <Plus className="h-3 w-3" />
                          {syncResult.summary.added} added
                        </span>
                      )}
                      {syncResult.summary.removed > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 rounded text-sm font-medium">
                          <Minus className="h-3 w-3" />
                          {syncResult.summary.removed} removed
                        </span>
                      )}
                      {syncResult.summary.modified > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-sm font-medium">
                          <Edit3 className="h-3 w-3" />
                          {syncResult.summary.modified} modified
                        </span>
                      )}
                      {syncResult.summary.added === 0 && syncResult.summary.removed === 0 && syncResult.summary.modified === 0 && (
                        <span className="text-sm text-green-600">No changes (all up to date)</span>
                      )}
                    </div>
                  )}

                  {/* Show changed configs */}
                  {(syncResult.added?.length || syncResult.modified?.length || syncResult.removed?.length) ? (
                    <div className="mt-3 space-y-2">
                      {syncResult.added && syncResult.added.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-green-700 mb-1">Added:</p>
                          {syncResult.added.slice(0, 3).map((c, i) => (
                            <p key={i} className="text-xs font-mono text-green-600 truncate">+ {c.path}</p>
                          ))}
                          {syncResult.added.length > 3 && (
                            <p className="text-xs text-green-600">... and {syncResult.added.length - 3} more</p>
                          )}
                        </div>
                      )}
                      {syncResult.modified && syncResult.modified.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-yellow-700 mb-1">Modified:</p>
                          {syncResult.modified.slice(0, 3).map((c, i) => (
                            <p key={i} className="text-xs font-mono text-yellow-600 truncate">~ {c.path}</p>
                          ))}
                          {syncResult.modified.length > 3 && (
                            <p className="text-xs text-yellow-600">... and {syncResult.modified.length - 3} more</p>
                          )}
                        </div>
                      )}
                      {syncResult.removed && syncResult.removed.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-red-700 mb-1">Removed:</p>
                          {syncResult.removed.slice(0, 3).map((c, i) => (
                            <p key={i} className="text-xs font-mono text-red-600 truncate">- {c.path}</p>
                          ))}
                          {syncResult.removed.length > 3 && (
                            <p className="text-xs text-red-600">... and {syncResult.removed.length - 3} more</p>
                          )}
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Error */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                <div>
                  <p className="font-medium text-red-800">Sync Failed</p>
                  <p className="text-sm text-red-600 mt-1">{error}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 border-b">
          <button
            onClick={() => setActiveView('changelog')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeView === 'changelog'
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            style={activeView === 'changelog' ? { borderColor: "hsl(var(--primary))" } : {}}
          >
            <Clock className="h-4 w-4 inline mr-2" />
            Sync History
          </button>
          <button
            onClick={() => setActiveView('changes')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeView === 'changes'
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            style={activeView === 'changes' ? { borderColor: "hsl(var(--primary))" } : {}}
          >
            <Edit3 className="h-4 w-4 inline mr-2" />
            Latest Changes
            {changelog[0]?.summary && (changelog[0].summary.added > 0 || changelog[0].summary.removed > 0 || changelog[0].summary.modified > 0) && (
              <span className="ml-2 px-1.5 py-0.5 text-xs bg-red-500 text-white rounded-full">
                {(changelog[0].summary.added || 0) + (changelog[0].summary.removed || 0) + (changelog[0].summary.modified || 0)}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveView('configs')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeView === 'configs'
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            style={activeView === 'configs' ? { borderColor: "hsl(var(--primary))" } : {}}
          >
            <Database className="h-4 w-4 inline mr-2" />
            Browse Configs
          </button>
          <button
            onClick={() => setActiveView('docs')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeView === 'docs'
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            style={activeView === 'docs' ? { borderColor: "hsl(var(--primary))" } : {}}
          >
            <BookOpen className="h-4 w-4 inline mr-2" />
            Config Docs
            {docsStatus?.docs_count ? (
              <span className="ml-2 px-1.5 py-0.5 text-xs bg-blue-500 text-white rounded-full">
                {docsStatus.docs_count}
              </span>
            ) : null}
          </button>
        </div>

        {/* Changelog View */}
        {activeView === 'changelog' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Sync History
              </CardTitle>
              <CardDescription>
                Track config changes and sync operations
              </CardDescription>
            </CardHeader>
            <CardContent>
              {changelog.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Clock className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>No sync history yet</p>
                  <p className="text-sm mt-1">Click "Sync Now" to fetch configs from ZooKeeper</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {changelog.map((entry, index) => {
                    const hasChanges = entry.summary && (entry.summary.added > 0 || entry.summary.removed > 0 || entry.summary.modified > 0);

                    return (
                      <div
                        key={index}
                        className="border rounded-lg p-4 hover:bg-muted/50 transition-colors"
                      >
                        <div
                          className="flex items-center justify-between cursor-pointer"
                          onClick={() => setExpandedEntry(expandedEntry === index ? null : index)}
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-2 h-2 rounded-full ${
                                hasChanges ? 'bg-green-500' : 'bg-gray-400'
                              }`}
                            />
                            <div>
                              <p className="font-medium">
                                {entry.total_configs} configs synced
                              </p>
                              {/* Summary badges */}
                              {entry.summary && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {entry.summary.added > 0 && (
                                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
                                      <Plus className="h-2.5 w-2.5" />
                                      {entry.summary.added}
                                    </span>
                                  )}
                                  {entry.summary.removed > 0 && (
                                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-xs font-medium">
                                      <Minus className="h-2.5 w-2.5" />
                                      {entry.summary.removed}
                                    </span>
                                  )}
                                  {entry.summary.modified > 0 && (
                                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-medium">
                                      <Edit3 className="h-2.5 w-2.5" />
                                      {entry.summary.modified}
                                    </span>
                                  )}
                                  {!hasChanges && (
                                    <span className="text-xs text-muted-foreground">No changes</span>
                                  )}
                                </div>
                              )}
                              <p className="text-sm text-muted-foreground">
                                {formatDate(entry.sync_time)}
                                <span className="ml-2 opacity-75">({formatRelativeTime(entry.sync_time)})</span>
                              </p>
                            </div>
                          </div>
                          {expandedEntry === index ? (
                            <ChevronUp className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          )}
                        </div>

                        {expandedEntry === index && (
                          <div className="mt-4 pt-4 border-t space-y-4">
                            {/* Added configs */}
                            {entry.added && entry.added.length > 0 && (
                              <div>
                                <p className="text-sm font-medium text-green-700 flex items-center gap-1 mb-2">
                                  <Plus className="h-4 w-4" />
                                  Added Configs ({entry.added.length})
                                </p>
                                <div className="space-y-1 max-h-32 overflow-y-auto">
                                  {entry.added.map((config, i) => (
                                    <div key={i} className="bg-green-50 rounded p-2">
                                      <p className="text-xs font-mono text-green-700 truncate">{config.path}</p>
                                      {config.preview && (
                                        <p className="text-xs text-green-600 mt-1 truncate">{config.preview}</p>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Modified configs */}
                            {entry.modified && entry.modified.length > 0 && (
                              <div>
                                <p className="text-sm font-medium text-yellow-700 flex items-center gap-1 mb-2">
                                  <Edit3 className="h-4 w-4" />
                                  Modified Configs ({entry.modified.length})
                                </p>
                                <div className="space-y-1 max-h-32 overflow-y-auto">
                                  {entry.modified.map((config, i) => (
                                    <div key={i} className="bg-yellow-50 rounded p-2">
                                      <p className="text-xs font-mono text-yellow-700 truncate">{config.path}</p>
                                      <div className="mt-1 text-xs">
                                        <p className="text-red-500 line-through truncate">- {config.old_preview}</p>
                                        <p className="text-green-600 truncate">+ {config.new_preview}</p>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Removed configs */}
                            {entry.removed && entry.removed.length > 0 && (
                              <div>
                                <p className="text-sm font-medium text-red-700 flex items-center gap-1 mb-2">
                                  <Minus className="h-4 w-4" />
                                  Removed Configs ({entry.removed.length})
                                </p>
                                <div className="space-y-1 max-h-32 overflow-y-auto">
                                  {entry.removed.map((config, i) => (
                                    <div key={i} className="bg-red-50 rounded p-2">
                                      <p className="text-xs font-mono text-red-700 truncate">{config.path}</p>
                                      {config.preview && (
                                        <p className="text-xs text-red-600 mt-1 truncate">{config.preview}</p>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Paths synced */}
                            <div>
                              <p className="text-sm font-medium mb-2">Paths synced:</p>
                              <div className="flex flex-wrap gap-2">
                                {entry.paths_synced.map((path, i) => (
                                  <span
                                    key={i}
                                    className="px-2 py-1 bg-muted rounded text-xs font-mono"
                                  >
                                    {path}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Latest Changes View */}
        {activeView === 'changes' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Edit3 className="h-5 w-5" />
                Latest Changes
              </CardTitle>
              <CardDescription>
                Changes detected in the most recent sync
                {changelog[0]?.sync_time && (
                  <span className="ml-2">({formatRelativeTime(changelog[0].sync_time)})</span>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!changelog[0] ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Edit3 className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>No sync data yet</p>
                  <p className="text-sm mt-1">Click "Sync Now" to fetch configs from ZooKeeper</p>
                </div>
              ) : !changelog[0].summary || (changelog[0].summary.added === 0 && changelog[0].summary.removed === 0 && changelog[0].summary.modified === 0) ? (
                <div className="text-center py-12 text-muted-foreground">
                  <CheckCircle className="h-12 w-12 mx-auto mb-3 text-green-500 opacity-75" />
                  <p className="text-lg font-medium text-foreground">No Changes Detected</p>
                  <p className="text-sm mt-1">All {changelog[0].total_configs} configs are up to date</p>
                  <p className="text-xs mt-2">Last synced: {formatDate(changelog[0].sync_time)}</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Summary Cards */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-center">
                      <Plus className="h-8 w-8 mx-auto text-green-600 mb-2" />
                      <p className="text-2xl font-bold text-green-700">{changelog[0].summary?.added || 0}</p>
                      <p className="text-sm text-green-600">Added</p>
                    </div>
                    <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-center">
                      <Edit3 className="h-8 w-8 mx-auto text-yellow-600 mb-2" />
                      <p className="text-2xl font-bold text-yellow-700">{changelog[0].summary?.modified || 0}</p>
                      <p className="text-sm text-yellow-600">Modified</p>
                    </div>
                    <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
                      <Minus className="h-8 w-8 mx-auto text-red-600 mb-2" />
                      <p className="text-2xl font-bold text-red-700">{changelog[0].summary?.removed || 0}</p>
                      <p className="text-sm text-red-600">Removed</p>
                    </div>
                  </div>

                  {/* Added Configs */}
                  {changelog[0].added && changelog[0].added.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-green-700 flex items-center gap-2 mb-3">
                        <Plus className="h-5 w-5" />
                        Added Configs ({changelog[0].added.length})
                      </h3>
                      <div className="space-y-2 space-y-2">
                        {changelog[0].added.map((config, i) => {
                          const key = `added-${i}`;
                          const isExpanded = expandedConfigs.has(key);
                          const configName = config.path.split('/').pop() || 'Config';

                          const isLoadingConfig = loadingConfigs.has(key);
                          const fullConfig = fullConfigCache[config.path];

                          return (
                            <div key={i} className="bg-green-50 border border-green-200 rounded-lg overflow-hidden">
                              <div
                                className="p-3 cursor-pointer hover:bg-green-100 transition-colors flex items-center justify-between"
                                onClick={() => toggleConfigExpand(key, config.path)}
                              >
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                  <Plus className="h-4 w-4 text-green-600 flex-shrink-0" />
                                  <div className="min-w-0">
                                    <span className="font-medium text-green-800">{configName}</span>
                                    <p className="text-xs text-green-600 font-mono truncate">{config.path}</p>
                                  </div>
                                </div>
                                {isLoadingConfig ? (
                                  <RefreshCw className="h-4 w-4 text-green-600 animate-spin flex-shrink-0" />
                                ) : isExpanded ? (
                                  <ChevronUp className="h-4 w-4 text-green-600 flex-shrink-0" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-green-600 flex-shrink-0" />
                                )}
                              </div>
                              {isExpanded && (
                                <div className="px-3 pb-3 border-t border-green-200 bg-green-100/50">
                                  {isLoadingConfig ? (
                                    <div className="mt-2 flex items-center justify-center py-4 text-green-600">
                                      <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                                      <span className="text-xs">Loading full config...</span>
                                    </div>
                                  ) : (
                                    <div className="mt-2 bg-white rounded border border-green-200 p-3">
                                      <pre className="text-xs font-mono text-green-700 whitespace-pre-wrap">
                                        {formatConfigData(fullConfig || config.preview || '')}
                                      </pre>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Modified Configs - Only show configs with computable diffs */}
                  {changelog[0].modified && changelog[0].modified.length > 0 && (() => {
                    const configsWithDiffs = changelog[0].modified
                      .map((config, i) => ({
                        config,
                        key: `modified-${i}`,
                        diff: config.old_preview && config.new_preview
                          ? computeDiff(config.old_preview, config.new_preview)
                          : null
                      }))
                      .filter(item => item.diff && (item.diff.added.length > 0 || item.diff.removed.length > 0 || item.diff.changed.length > 0));

                    if (configsWithDiffs.length === 0) return null;

                    return (
                      <div>
                        <h3 className="text-lg font-semibold text-yellow-700 flex items-center gap-2 mb-3">
                          <Edit3 className="h-5 w-5" />
                          Modified Configs ({configsWithDiffs.length})
                        </h3>
                        <div className="space-y-2">
                          {configsWithDiffs.map(({ config, key, diff }) => {
                            const isExpanded = expandedConfigs.has(key);
                            const configName = config.path.split('/').pop() || 'Config';
                            const totalChanges = diff!.changed.length + diff!.added.length + diff!.removed.length;

                            return (
                              <div key={key} className="bg-yellow-50 border border-yellow-200 rounded-lg overflow-hidden">
                                <div
                                  className="p-3 cursor-pointer hover:bg-yellow-100 transition-colors flex items-center justify-between"
                                  onClick={() => toggleConfigExpand(key)}
                                >
                                  <div className="flex items-center gap-3 flex-1 min-w-0">
                                    <Edit3 className="h-4 w-4 text-yellow-600 flex-shrink-0" />
                                    <div className="min-w-0 flex-1">
                                      <div className="flex items-center gap-2">
                                        <span className="font-medium text-yellow-800">{configName}</span>
                                        <span className="text-xs text-yellow-600 bg-yellow-100 px-2 py-0.5 rounded">
                                          {totalChanges} changes
                                        </span>
                                      </div>
                                      <p className="text-xs text-yellow-600 font-mono truncate">{config.path}</p>
                                    </div>
                                  </div>
                                  {isExpanded ? (
                                    <ChevronUp className="h-4 w-4 text-yellow-600 flex-shrink-0" />
                                  ) : (
                                    <ChevronDown className="h-4 w-4 text-yellow-600 flex-shrink-0" />
                                  )}
                                </div>
                                {isExpanded && (
                                  <div className="px-3 pb-3 border-t border-yellow-200 bg-yellow-100/50">
                                    <div className="mt-2 space-y-1">
                                      {diff!.changed.map((change, idx) => (
                                        <div key={idx} className="text-xs">
                                          <span className="font-medium text-yellow-700">{change.key}: </span>
                                          <span className="font-mono text-red-500 line-through">{change.old}</span>
                                          <span className="text-gray-400 mx-1">→</span>
                                          <span className="font-mono text-green-600">{change.new}</span>
                                        </div>
                                      ))}
                                      {diff!.added.map((added, idx) => (
                                        <p key={`added-${idx}`} className="text-xs font-mono text-green-600">+ {added}</p>
                                      ))}
                                      {diff!.removed.map((removed, idx) => (
                                        <p key={`removed-${idx}`} className="text-xs font-mono text-red-500">- {removed}</p>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Removed Configs */}
                  {changelog[0].removed && changelog[0].removed.length > 0 && (
                    <div>
                      <h3 className="text-lg font-semibold text-red-700 flex items-center gap-2 mb-3">
                        <Minus className="h-5 w-5" />
                        Removed Configs ({changelog[0].removed.length})
                      </h3>
                      <div className="space-y-2 space-y-2">
                        {changelog[0].removed.map((config, i) => {
                          const key = `removed-${i}`;
                          const isExpanded = expandedConfigs.has(key);
                          const configName = config.path.split('/').pop() || 'Config';

                          return (
                            <div key={i} className="bg-red-50 border border-red-200 rounded-lg overflow-hidden">
                              <div
                                className="p-3 cursor-pointer hover:bg-red-100 transition-colors flex items-center justify-between"
                                onClick={() => toggleConfigExpand(key)}
                              >
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                  <Minus className="h-4 w-4 text-red-600 flex-shrink-0" />
                                  <div className="min-w-0">
                                    <span className="font-medium text-red-800">{configName}</span>
                                    <p className="text-xs text-red-600 font-mono truncate">{config.path}</p>
                                  </div>
                                </div>
                                {isExpanded ? (
                                  <ChevronUp className="h-4 w-4 text-red-600 flex-shrink-0" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-red-600 flex-shrink-0" />
                                )}
                              </div>
                              {isExpanded && (
                                <div className="px-3 pb-3 border-t border-red-200 bg-red-100/50">
                                  <div className="mt-2 bg-white rounded border border-red-200 p-3">
                                    <pre className="text-xs font-mono text-red-600 whitespace-pre-wrap">
                                      {formatConfigData(config.preview || '')}
                                    </pre>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Configs View */}
        {activeView === 'configs' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Browse Configs
              </CardTitle>
              <CardDescription>
                Search and explore indexed ZooKeeper configurations
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Search */}
              <div className="relative mb-6">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search configs (e.g., payment, chat, notification)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm"
                />
              </div>

              {/* Config List */}
              {configs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Database className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>No configs found</p>
                  <p className="text-sm mt-1">Try a different search term or sync configs first</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {configs.map((config, index) => {
                    const key = `config-${index}`;
                    const isExpanded = expandedConfigs.has(key);
                    return (
                      <div
                        key={index}
                        className="border rounded-xl overflow-hidden hover:shadow-md transition-shadow"
                      >
                        {/* Header - Clickable */}
                        <div
                          className="bg-muted/30 px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-muted/50 transition-colors"
                          onClick={() => toggleConfigExpand(key)}
                        >
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div
                              className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
                              style={{ backgroundColor: "hsl(var(--primary))" }}
                            >
                              {config.config_name?.charAt(0)?.toUpperCase() || 'C'}
                            </div>
                            <div className="flex-1 min-w-0">
                              <h4 className="font-semibold text-foreground">{config.config_name}</h4>
                              <p className="text-xs text-muted-foreground font-mono truncate">{config.path}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span
                              className="px-2.5 py-1 text-xs font-medium rounded-full"
                              style={{ backgroundColor: "hsl(var(--primary) / 0.1)", color: "hsl(var(--primary))" }}
                            >
                              {config.category}
                            </span>
                            {config.score && (
                              <span className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded-full font-medium">
                                {(config.score * 100).toFixed(0)}%
                              </span>
                            )}
                            {isExpanded ? (
                              <ChevronUp className="h-5 w-5 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="h-5 w-5 text-muted-foreground" />
                            )}
                          </div>
                        </div>

                        {/* Config Data - Expandable */}
                        {isExpanded && (
                          <div className="p-4 border-t bg-background">
                            <p className="text-xs font-medium text-muted-foreground mb-2">Full Configuration Value:</p>
                            <div className="bg-muted/30 rounded-lg p-4 max-h-80 overflow-auto border">
                              <pre className="text-sm font-mono text-foreground whitespace-pre-wrap break-words">
                                {formatConfigData(config.text)}
                              </pre>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Config Docs View - Improved with Master-Detail Layout */}
        {activeView === 'docs' && (
          <div className="space-y-4">
            {/* Header Card with Upload */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div
                      className="w-12 h-12 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: "hsl(var(--primary) / 0.1)" }}
                    >
                      <BookOpen className="h-6 w-6" style={{ color: "hsl(var(--primary))" }} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">Config Documentation</h3>
                      {docsStatus?.source_file ? (
                        <p className="text-sm text-muted-foreground">
                          {docsStatus.source_file} • Updated {docsStatus.last_updated ? new Date(docsStatus.last_updated).toLocaleDateString() : 'N/A'}
                        </p>
                      ) : (
                        <p className="text-sm text-muted-foreground">Upload ZK_CONFIG_BEHAVIOR_GUIDE.md to get started</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="text-2xl font-bold" style={{ color: "hsl(var(--primary))" }}>
                        {configDocs.length}
                      </p>
                      <p className="text-xs text-muted-foreground">Configs Documented</p>
                    </div>
                    <input
                      type="file"
                      accept=".md"
                      onChange={handleDocsUpload}
                      ref={fileInputRef}
                      className="hidden"
                    />
                    <Button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploadingDocs}
                      size="sm"
                    >
                      {isUploadingDocs ? (
                        <>
                          <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                          Uploading...
                        </>
                      ) : (
                        <>
                          <Upload className="h-4 w-4 mr-2" />
                          Upload MD
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                {/* Category Chips */}
                {docsStatus?.categories && Object.keys(docsStatus.categories).length > 0 && (
                  <div className="mt-4 pt-4 border-t">
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => {
                          setSelectedCategory(null);
                          setDocsCurrentPage(1);
                        }}
                        className={`px-3 py-1.5 text-xs font-medium rounded-full transition-all ${
                          selectedCategory === null
                            ? 'text-white shadow-md'
                            : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                        }`}
                        style={selectedCategory === null ? { backgroundColor: "hsl(var(--primary))" } : {}}
                      >
                        All ({configDocs.length})
                      </button>
                      {(showAllCategories
                        ? Object.entries(docsStatus.categories)
                        : Object.entries(docsStatus.categories).slice(0, 6)
                      ).map(([category, configs]) => (
                        <button
                          key={category}
                          onClick={() => {
                            setSelectedCategory(category);
                            setDocsCurrentPage(1);
                            setSelectedConfig(null);
                          }}
                          className={`px-3 py-1.5 text-xs font-medium rounded-full transition-all ${
                            selectedCategory === category
                              ? 'text-white shadow-md'
                              : 'bg-muted hover:bg-muted/80 text-muted-foreground'
                          }`}
                          style={selectedCategory === category ? { backgroundColor: "hsl(var(--primary))" } : {}}
                        >
                          {category.length > 20 ? category.substring(0, 20) + '...' : category} ({(configs as string[]).length})
                        </button>
                      ))}
                      {Object.keys(docsStatus.categories).length > 6 && (
                        <button
                          onClick={() => setShowAllCategories(!showAllCategories)}
                          className="px-3 py-1.5 text-xs font-medium rounded-full bg-blue-50 text-blue-600 hover:bg-blue-100 transition-all"
                        >
                          {showAllCategories ? 'Show Less' : `+${Object.keys(docsStatus.categories).length - 6} more`}
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Search Bar */}
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search configs by name, behavior, or keyword..."
                value={docsSearchQuery}
                onChange={(e) => {
                  setDocsSearchQuery(e.target.value);
                  setDocsCurrentPage(1);
                }}
                className="w-full pl-12 pr-4 py-3.5 border rounded-xl bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm shadow-sm"
              />
            </div>

            {/* Master-Detail Layout */}
            {configDocs.length === 0 ? (
              <Card>
                <CardContent className="py-12">
                  <div className="text-center text-muted-foreground">
                    <FileText className="h-16 w-16 mx-auto mb-4 opacity-30" />
                    <p className="text-lg font-medium">No Config Documentation</p>
                    <p className="text-sm mt-1">Upload ZK_CONFIG_BEHAVIOR_GUIDE.md to browse configs</p>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Config List (Left Panel) */}
                <Card className="lg:max-h-[600px] lg:overflow-hidden flex flex-col">
                  <CardHeader className="pb-3 flex-shrink-0">
                    <CardTitle className="text-base">
                      {selectedCategory || 'All Configs'}
                    </CardTitle>
                    <CardDescription>
                      {(() => {
                        const filteredDocs = selectedCategory
                          ? configDocs.filter(d => d.category === selectedCategory)
                          : configDocs;
                        const totalPages = Math.ceil(filteredDocs.length / DOCS_PER_PAGE);
                        return `Page ${docsCurrentPage} of ${totalPages} • ${filteredDocs.length} configs`;
                      })()}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex-1 overflow-y-auto pb-3">
                    <div className="space-y-2">
                      {(() => {
                        const filteredDocs = selectedCategory
                          ? configDocs.filter(d => d.category === selectedCategory)
                          : configDocs;
                        const startIdx = (docsCurrentPage - 1) * DOCS_PER_PAGE;
                        const paginatedDocs = filteredDocs.slice(startIdx, startIdx + DOCS_PER_PAGE);

                        return paginatedDocs.map((doc) => {
                          const isSelected = selectedConfig?.config_name === doc.config_name;
                          return (
                            <div
                              key={doc.config_name}
                              onClick={() => setSelectedConfig(doc)}
                              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                                isSelected
                                  ? 'border-primary bg-primary/5 shadow-sm'
                                  : 'hover:bg-muted/50 hover:border-muted-foreground/20'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <code className="text-sm font-mono font-semibold text-foreground truncate">
                                      {doc.config_name}
                                    </code>
                                  </div>
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span
                                      className="px-2 py-0.5 text-xs font-medium rounded"
                                      style={{
                                        backgroundColor: doc.config_type === 'boolean' ? 'hsl(var(--primary) / 0.1)' :
                                                        doc.config_type === 'number' ? 'rgb(234 179 8 / 0.1)' :
                                                        doc.config_type === 'object' ? 'rgb(168 85 247 / 0.1)' :
                                                        'rgb(107 114 128 / 0.1)',
                                        color: doc.config_type === 'boolean' ? 'hsl(var(--primary))' :
                                               doc.config_type === 'number' ? 'rgb(161 98 7)' :
                                               doc.config_type === 'object' ? 'rgb(126 34 206)' :
                                               'rgb(75 85 99)'
                                      }}
                                    >
                                      {doc.config_type}
                                    </span>
                                    {doc.default_value && (
                                      <span className="text-xs text-muted-foreground">
                                        Default: <code className="font-mono">{doc.default_value}</code>
                                      </span>
                                    )}
                                  </div>
                                  {!selectedCategory && (
                                    <p className="text-xs text-muted-foreground mt-1 truncate">
                                      {doc.category}
                                    </p>
                                  )}
                                </div>
                                <ChevronDown className={`h-4 w-4 text-muted-foreground flex-shrink-0 transition-transform ${isSelected ? 'rotate-180' : ''}`} />
                              </div>
                            </div>
                          );
                        });
                      })()}
                    </div>
                  </CardContent>
                  {/* Pagination */}
                  {(() => {
                    const filteredDocs = selectedCategory
                      ? configDocs.filter(d => d.category === selectedCategory)
                      : configDocs;
                    const totalPages = Math.ceil(filteredDocs.length / DOCS_PER_PAGE);

                    if (totalPages <= 1) return null;

                    return (
                      <div className="px-6 py-3 border-t flex items-center justify-between bg-muted/20 flex-shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setDocsCurrentPage(p => Math.max(1, p - 1))}
                          disabled={docsCurrentPage === 1}
                        >
                          Previous
                        </Button>
                        <div className="flex items-center gap-1">
                          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            let pageNum;
                            if (totalPages <= 5) {
                              pageNum = i + 1;
                            } else if (docsCurrentPage <= 3) {
                              pageNum = i + 1;
                            } else if (docsCurrentPage >= totalPages - 2) {
                              pageNum = totalPages - 4 + i;
                            } else {
                              pageNum = docsCurrentPage - 2 + i;
                            }
                            return (
                              <button
                                key={pageNum}
                                onClick={() => setDocsCurrentPage(pageNum)}
                                className={`w-8 h-8 text-xs font-medium rounded-lg transition-all ${
                                  docsCurrentPage === pageNum
                                    ? 'text-white shadow'
                                    : 'hover:bg-muted'
                                }`}
                                style={docsCurrentPage === pageNum ? { backgroundColor: "hsl(var(--primary))" } : {}}
                              >
                                {pageNum}
                              </button>
                            );
                          })}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setDocsCurrentPage(p => Math.min(totalPages, p + 1))}
                          disabled={docsCurrentPage === totalPages}
                        >
                          Next
                        </Button>
                      </div>
                    );
                  })()}
                </Card>

                {/* Config Detail (Right Panel) */}
                <Card className="lg:max-h-[600px] lg:overflow-y-auto">
                  {selectedConfig ? (
                    <>
                      <CardHeader className="pb-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <CardTitle className="font-mono text-lg break-all">
                              {selectedConfig.config_name}
                            </CardTitle>
                            <CardDescription className="mt-1">
                              {selectedConfig.category}
                            </CardDescription>
                          </div>
                          <span
                            className="px-3 py-1 text-sm font-medium rounded-lg flex-shrink-0"
                            style={{
                              backgroundColor: selectedConfig.config_type === 'boolean' ? 'hsl(var(--primary) / 0.1)' :
                                              selectedConfig.config_type === 'number' ? 'rgb(234 179 8 / 0.1)' :
                                              selectedConfig.config_type === 'object' ? 'rgb(168 85 247 / 0.1)' :
                                              'rgb(107 114 128 / 0.1)',
                              color: selectedConfig.config_type === 'boolean' ? 'hsl(var(--primary))' :
                                     selectedConfig.config_type === 'number' ? 'rgb(161 98 7)' :
                                     selectedConfig.config_type === 'object' ? 'rgb(126 34 206)' :
                                     'rgb(75 85 99)'
                            }}
                          >
                            {selectedConfig.config_type}
                          </span>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-5">
                        {/* Default Value */}
                        {selectedConfig.default_value && (
                          <div className="p-4 rounded-lg bg-green-50 border border-green-200">
                            <p className="text-xs font-semibold text-green-700 mb-1">Default Value</p>
                            <code className="text-lg font-mono font-bold text-green-800">
                              {selectedConfig.default_value}
                            </code>
                          </div>
                        )}

                        {/* Description */}
                        {selectedConfig.description && (
                          <div>
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Description</p>
                            <p className="text-sm text-foreground leading-relaxed">{selectedConfig.description}</p>
                          </div>
                        )}

                        {/* Behavioral Impact */}
                        {selectedConfig.behavioral_impact && (
                          <div>
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Behavioral Impact</p>
                            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                              <p className="text-sm text-blue-900 leading-relaxed">{selectedConfig.behavioral_impact}</p>
                            </div>
                          </div>
                        )}

                        {/* Examples */}
                        {selectedConfig.examples && selectedConfig.examples.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                              Value → Effect Examples
                            </p>
                            <div className="space-y-2">
                              {selectedConfig.examples.map((ex, idx) => (
                                <div
                                  key={idx}
                                  className="p-3 rounded-lg border bg-muted/30 flex items-start gap-3"
                                >
                                  <code
                                    className="px-2 py-1 rounded text-sm font-mono font-semibold flex-shrink-0"
                                    style={{ backgroundColor: "hsl(var(--primary) / 0.1)", color: "hsl(var(--primary))" }}
                                  >
                                    {ex.value}
                                  </code>
                                  <div className="flex-1 min-w-0">
                                    <span className="text-sm text-foreground" dangerouslySetInnerHTML={{ __html: ex.effect.replace(/<br>/g, ' • ') }} />
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Implementation Reference */}
                        {selectedConfig.implementation_ref && (
                          <div>
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Implementation</p>
                            <code className="text-sm font-mono px-3 py-2 rounded-lg bg-muted block">
                              {selectedConfig.implementation_ref}
                            </code>
                          </div>
                        )}

                        {/* Related Configs */}
                        {selectedConfig.related_configs && selectedConfig.related_configs.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Related Configs</p>
                            <div className="flex flex-wrap gap-2">
                              {selectedConfig.related_configs.map((rel, idx) => (
                                <button
                                  key={idx}
                                  onClick={() => {
                                    const relDoc = configDocs.find(d => d.config_name === rel);
                                    if (relDoc) setSelectedConfig(relDoc);
                                  }}
                                  className="px-2 py-1 text-xs font-mono rounded bg-muted hover:bg-muted/80 transition-colors"
                                >
                                  {rel}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </>
                  ) : (
                    <CardContent className="py-16">
                      <div className="text-center text-muted-foreground">
                        <Settings className="h-12 w-12 mx-auto mb-4 opacity-30" />
                        <p className="font-medium">Select a Config</p>
                        <p className="text-sm mt-1">Click on a config from the list to view details</p>
                      </div>
                    </CardContent>
                  )}
                </Card>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
