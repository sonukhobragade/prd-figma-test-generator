import { useState, useEffect, useCallback } from 'react';
import {
  Search,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  FileText,
  AlertCircle,
  CheckCircle2,
  FolderOpen,
  Folder,
  Monitor,
  Server,
  Filter,
  Eye,
  X,
  TestTube2,
  Clock,
  Tag,
  Hash,
  Palette,
  Image,
  Smartphone,
  Settings,
  ListChecks,
  type LucideIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

// Types - Professional QA Test Case Format
interface TestCase {
  id: string;
  test_case_id: string;
  feature: string;
  priority: string;
  category: string;
  user_type: string;
  screen_reference: string;
  precondition: string;
  test_scenario: string;
  steps_to_execute: string;
  expected_result: string;
  dev_status: string;
  qa_status: string;
  comments: string;
  requirement_description: string;
  test_step: string;
  test_type: string;
  session_id: string;
  feature_type_detected: string;
  user_states: string[];
  screens_involved: string[];
  coverage_score: number;
  generated_at: string;
  // Backend-specific fields
  subcategory?: string;
  api_component?: string;
  verification_method?: string;
}

// Truth Table Entry type
interface TruthTableEntry {
  id: string;
  entry_id: string;
  session_id: string;
  feature_name: string;
  screen: string;
  checkpoint: string;
  failed_redirect: string;
  pending_redirect: string;
  successful_redirect: string;
  auto_redirect_failed: string;
  auto_redirect_pending: string;
  auto_redirect_success: string;
  result: string;
  expected: string;
  feature: string;
  priority: string;
  test_type: string;
  version: number;
  generated_at: string;
}

// Version within a feature
interface FeatureVersion {
  version: number;
  session_id: string;
  documents_included: string[];
  frontend_count: number;
  backend_count: number;
  last_updated: string;
}

// Feature with versions
interface Feature {
  feature_name: string;
  versions: FeatureVersion[];
}

// Document type badge mapping with SVG icons
const documentBadges: Record<string, { Icon: LucideIcon; label: string; color: string }> = {
  prd: { Icon: FileText, label: 'PRD', color: 'bg-blue-100 text-blue-700' },
  figma: { Icon: Palette, label: 'Figma', color: 'bg-purple-100 text-purple-700' },
  screenshot: { Icon: Image, label: 'Screenshot', color: 'bg-pink-100 text-pink-700' },
  frontend_lld: { Icon: Smartphone, label: 'Frontend LLD', color: 'bg-green-100 text-green-700' },
  backend_lld: { Icon: Settings, label: 'Backend LLD', color: 'bg-orange-100 text-orange-700' },
};

interface RAGStatus {
  enabled: boolean;
  health: string;
  test_cases: { count: number };
  total_documents: number;
}

// Backend test types - used to separate backend from frontend tests
const BACKEND_TEST_TYPES = ['API', 'DATABASE', 'SECURITY', 'PERFORMANCE', 'CONFIG', 'ANALYTICS', 'BACKEND', 'CACHE'];

// Priority badge styles
const priorityStyles: Record<string, { bg: string; text: string; border: string }> = {
  P0: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  P1: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  P2: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  P3: { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-200' },
};

// Test type styles
const testTypeStyles: Record<string, string> = {
  positive: 'bg-emerald-50 text-emerald-700',
  negative: 'bg-red-50 text-red-700',
  edge_case: 'bg-violet-50 text-violet-700',
  boundary: 'bg-blue-50 text-blue-700',
  API: 'bg-indigo-50 text-indigo-700',
  DATABASE: 'bg-cyan-50 text-cyan-700',
  SECURITY: 'bg-rose-50 text-rose-700',
  PERFORMANCE: 'bg-orange-50 text-orange-700',
};

export function TestRepository() {
  // New feature/version state
  const [features, setFeatures] = useState<Feature[]>([]);
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [selectedFeatureName, setSelectedFeatureName] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<FeatureVersion | null>(null);
  const [expandedFeatures, setExpandedFeatures] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [filterPriority, setFilterPriority] = useState<string | null>(null);
  const [filterTestType, setFilterTestType] = useState<string | null>(null);
  const [filterScope, setFilterScope] = useState<'all' | 'frontend' | 'backend'>('all');
  const [loading, setLoading] = useState(true);
  const [loadingTests, setLoadingTests] = useState(false);
  const [ragStatus, setRagStatus] = useState<RAGStatus | null>(null);
  const [selectedTestCase, setSelectedTestCase] = useState<TestCase | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [truthTableEntries, setTruthTableEntries] = useState<TruthTableEntry[]>([]);
  const [viewMode, setViewMode] = useState<'test_cases' | 'truth_table'>('test_cases');
  const [loadingTruthTable, setLoadingTruthTable] = useState(false);

  // Helper function to escape CSV values - preserves newlines with proper quoting
  const escapeCSV = (value: string | undefined | null): string => {
    if (!value) return '';
    const str = String(value);
    // Always wrap in quotes and escape internal quotes for multiline support
    // This ensures Excel/Sheets properly handle multiline content
    return `"${str.replace(/"/g, '""')}"`;
  };

  // Helper function to format test type to Title Case
  const formatTestType = (testType: string | undefined | null): string => {
    if (!testType) return '';
    return testType
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };

  // Fetch RAG status
  const fetchRAGStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/rag/status');
      const data = await response.json();
      setRagStatus(data);
    } catch (err) {
      console.error('Failed to fetch RAG status:', err);
    }
  }, []);

  // Fetch features (new versioned structure)
  const fetchFeatures = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/rag/features');
      const data = await response.json();
      if (data.success) {
        setFeatures(data.features);
        // Auto-select first feature and its latest version
        if (data.features.length > 0) {
          const firstFeature = data.features[0];
          setExpandedFeatures(new Set([firstFeature.feature_name]));
          setSelectedFeatureName(firstFeature.feature_name);
          // Select latest version
          if (firstFeature.versions.length > 0) {
            const latestVersion = firstFeature.versions[firstFeature.versions.length - 1];
            setSelectedVersion(latestVersion);
          }
        }
      }
    } catch (err) {
      console.error('Failed to fetch features:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch test cases for selected version
  const fetchTestCases = useCallback(async () => {
    if (!selectedVersion) {
      setTestCases([]);
      return;
    }
    setLoadingTests(true);
    try {
      const params = new URLSearchParams();
      params.append('session_id', selectedVersion.session_id);
      if (filterPriority) params.append('priority', filterPriority);
      if (filterTestType) params.append('test_type', filterTestType);
      if (filterScope !== 'all') params.append('test_scope', filterScope);
      params.append('limit', '500');

      const response = await fetch(`/api/rag/test-cases?${params}`);
      const data = await response.json();
      if (data.success) {
        setTestCases(data.test_cases);
      }
    } catch (err) {
      console.error('Failed to fetch test cases:', err);
    } finally {
      setLoadingTests(false);
    }
  }, [selectedVersion, filterPriority, filterTestType, filterScope]);

  // Fetch truth table entries for selected version
  const fetchTruthTable = useCallback(async () => {
    if (!selectedVersion) {
      setTruthTableEntries([]);
      return;
    }
    setLoadingTruthTable(true);
    try {
      const params = new URLSearchParams();
      params.append('session_id', selectedVersion.session_id);
      params.append('limit', '500');

      const response = await fetch(`/api/rag/truth-table?${params}`);
      const data = await response.json();
      if (data.success) {
        setTruthTableEntries(data.entries);
      }
    } catch (err) {
      console.error('Failed to fetch truth table:', err);
    } finally {
      setLoadingTruthTable(false);
    }
  }, [selectedVersion]);

  useEffect(() => {
    fetchRAGStatus();
    fetchFeatures();
  }, [fetchRAGStatus, fetchFeatures]);

  useEffect(() => {
    fetchTestCases();
  }, [fetchTestCases]);

  useEffect(() => {
    fetchTruthTable();
  }, [fetchTruthTable]);

  // Toggle feature expansion
  const toggleFeature = (featureName: string) => {
    setExpandedFeatures(prev => {
      const next = new Set(prev);
      if (next.has(featureName)) next.delete(featureName);
      else next.add(featureName);
      return next;
    });
  };

  // Select feature and optionally a specific version
  const handleSelectFeature = (featureName: string) => {
    setSelectedFeatureName(featureName);
    // Find the feature and select its latest version
    const feature = features.find(f => f.feature_name === featureName);
    if (feature && feature.versions.length > 0) {
      const latestVersion = feature.versions[feature.versions.length - 1];
      setSelectedVersion(latestVersion);
    }
    if (!expandedFeatures.has(featureName)) toggleFeature(featureName);
  };

  // Select specific version
  const handleSelectVersion = (featureName: string, version: FeatureVersion) => {
    setSelectedFeatureName(featureName);
    setSelectedVersion(version);
  };

  // Filter test cases
  const filteredTestCases = testCases.filter(tc => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    const scenario = tc.test_scenario || tc.requirement_description || '';
    return (
      scenario.toLowerCase().includes(query) ||
      tc.feature.toLowerCase().includes(query) ||
      tc.test_case_id.toLowerCase().includes(query) ||
      (tc.category || '').toLowerCase().includes(query)
    );
  });

  // Separate frontend and backend test cases
  const frontendTestCases = filteredTestCases.filter(
    tc => !BACKEND_TEST_TYPES.includes(tc.test_type?.toUpperCase() || '')
  );
  const backendTestCases = filteredTestCases.filter(
    tc => BACKEND_TEST_TYPES.includes(tc.test_type?.toUpperCase() || '')
  );

  // Export CSV functions
  const exportFrontendCSV = () => {
    if (frontendTestCases.length === 0) return;
    const headers = ['Test Case ID', 'Priority', 'Category', 'User Type', 'Screen Reference', 'Precondition', 'Test Scenario', 'Steps to Execute', 'Expected Result', 'Dev Status', 'QA Status', 'Comments'];
    const rows = frontendTestCases.map(tc => [
      escapeCSV(tc.test_case_id), escapeCSV(tc.priority), escapeCSV(tc.category || 'General'), escapeCSV(tc.user_type || 'Any'),
      escapeCSV(tc.screen_reference), escapeCSV(tc.precondition), escapeCSV(tc.test_scenario || tc.requirement_description),
      escapeCSV(tc.steps_to_execute || tc.test_step), escapeCSV(tc.expected_result), escapeCSV(tc.dev_status || 'Not Started'),
      escapeCSV(tc.qa_status || 'Not Started'), escapeCSV(tc.comments)
    ].join(','));
    downloadCSV([headers.join(','), ...rows].join('\n'), 'Frontend');
  };

  const exportBackendCSV = () => {
    if (backendTestCases.length === 0) return;
    // Match exact server format: BackendTestCase.csv_header() with tracking columns
    const headers = ['Test Case ID', 'Category', 'Subcategory', 'API/Component', 'Test Scenario', 'Precondition', 'Verification Method', 'Expected Result', 'Priority', 'Test Type', 'DEV Status', 'QA Status', 'Comments'];
    const rows = backendTestCases.map(tc => [
      escapeCSV(tc.test_case_id),
      escapeCSV(tc.category || 'General'),
      escapeCSV(tc.subcategory || tc.user_type || ''),
      escapeCSV(tc.api_component || tc.screen_reference || ''),
      escapeCSV(tc.test_scenario || tc.requirement_description),
      escapeCSV(tc.precondition),
      escapeCSV(tc.verification_method || tc.steps_to_execute || tc.test_step),
      escapeCSV(tc.expected_result),
      escapeCSV(tc.priority),
      escapeCSV(tc.test_type),
      escapeCSV(tc.dev_status || ''),
      escapeCSV(tc.qa_status || ''),
      escapeCSV(tc.comments || '')
    ].join(','));
    downloadCSV([headers.join(','), ...rows].join('\n'), 'Backend');
  };

  const downloadCSV = (content: string, name: string) => {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;

    // Format: Name_FeatureName_Epoch.csv
    const epoch = Date.now();
    // Sanitize feature name: replace spaces with underscores, remove special chars
    const featureName = selectedFeatureName
      ? selectedFeatureName.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '')
      : 'Unknown';

    link.download = `${name}_${featureName}_${epoch}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const availableTestTypes = [...new Set(testCases.map(tc => tc.test_type))];

  // Clear all filters
  const clearFilters = () => {
    setSearchQuery('');
    setFilterPriority(null);
    setFilterTestType(null);
  };

  const hasActiveFilters = searchQuery || filterPriority || filterTestType || filterScope !== 'all';

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-slate-50">
      {/* Sidebar */}
      <div className="w-72 bg-white border-r border-slate-200 flex flex-col">
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Features</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { fetchRAGStatus(); fetchFeatures(); }}
              className="h-7 w-7 p-0 text-slate-400 hover:text-slate-600"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
          {/* RAG Status */}
          {ragStatus && (
            <div className={`flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-md ${
              ragStatus.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
            }`}>
              {ragStatus.enabled ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
              <span className="font-medium">{ragStatus.test_cases?.count || 0} test cases indexed</span>
            </div>
          )}
        </div>

        {/* Features Tree */}
        <div className="flex-1 overflow-y-auto p-2">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-400">
              <RefreshCw className="h-5 w-5 animate-spin mb-2" />
              <span className="text-xs">Loading...</span>
            </div>
          ) : features.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center px-4">
              <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-3">
                <TestTube2 className="h-6 w-6 text-slate-400" />
              </div>
              <p className="text-sm font-medium text-slate-600 mb-1">No Features</p>
              <p className="text-xs text-slate-400">Generate test cases to see them here</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {features.map(feature => {
                const totalTests = feature.versions.reduce((sum, v) => sum + v.frontend_count + v.backend_count, 0);
                return (
                  <div key={feature.feature_name}>
                    {/* Feature Row */}
                    <button
                      onClick={() => handleSelectFeature(feature.feature_name)}
                      className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-left transition-colors group ${
                        selectedFeatureName === feature.feature_name
                          ? 'bg-blue-50 text-blue-700'
                          : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleFeature(feature.feature_name); }}
                        className="p-0.5 rounded hover:bg-slate-200/50"
                      >
                        {expandedFeatures.has(feature.feature_name)
                          ? <ChevronDown className="h-4 w-4 text-slate-400" />
                          : <ChevronRight className="h-4 w-4 text-slate-400" />
                        }
                      </button>
                      {expandedFeatures.has(feature.feature_name)
                        ? <FolderOpen className="h-4 w-4 text-amber-500" />
                        : <Folder className="h-4 w-4 text-amber-500" />
                      }
                      <span className="flex-1 truncate text-sm font-medium">{feature.feature_name}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        selectedFeatureName === feature.feature_name
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-slate-100 text-slate-500'
                      }`}>
                        {totalTests}
                      </span>
                    </button>

                    {/* Versions */}
                    {expandedFeatures.has(feature.feature_name) && (
                      <div className="ml-7 mt-0.5 space-y-0.5 border-l border-slate-200 pl-2">
                        {feature.versions.map(version => (
                          <button
                            key={version.session_id}
                            onClick={() => handleSelectVersion(feature.feature_name, version)}
                            className={`w-full flex flex-col gap-1.5 px-2.5 py-2 rounded text-left text-xs transition-colors ${
                              selectedVersion?.session_id === version.session_id
                                ? 'bg-blue-50 text-blue-600'
                                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                            }`}
                          >
                            {/* Version header */}
                            <div className="flex items-center gap-2 w-full">
                              <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                              <span className="font-medium">V{version.version}</span>
                              <div className="flex-1" />
                              {/* Test counts */}
                              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-100 text-blue-600 text-[10px]">
                                <Monitor className="h-3 w-3" />
                                {version.frontend_count}
                              </span>
                              {version.backend_count > 0 && (
                                <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-600 text-[10px]">
                                  <Server className="h-3 w-3" />
                                  {version.backend_count}
                                </span>
                              )}
                            </div>
                            {/* Document badges */}
                            <div className="flex flex-wrap gap-1 ml-5">
                              {version.documents_included.map(doc => {
                                const badge = documentBadges[doc];
                                if (!badge) return null;
                                const { Icon, label, color } = badge;
                                return (
                                  <span
                                    key={doc}
                                    className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] ${color}`}
                                    title={label}
                                  >
                                    <Icon className="h-3 w-3" />
                                    <span>{label}</span>
                                  </span>
                                );
                              })}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="bg-white border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-3">
            {/* Search */}
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search test cases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-md bg-slate-50 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>

            {/* Filter Toggle */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className={`gap-2 ${showFilters ? 'bg-slate-100' : ''}`}
            >
              <Filter className="h-4 w-4" />
              Filters
              {hasActiveFilters && (
                <span className="w-2 h-2 rounded-full bg-blue-500" />
              )}
            </Button>

            {/* Clear Filters */}
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="text-slate-500">
                <X className="h-4 w-4 mr-1" />
                Clear
              </Button>
            )}

            <div className="h-6 w-px bg-slate-200" />

            {/* Export Buttons */}
            <Button
              variant="outline"
              size="sm"
              onClick={exportFrontendCSV}
              disabled={frontendTestCases.length === 0}
              className="gap-2"
            >
              <Monitor className="h-4 w-4" />
              Frontend ({frontendTestCases.length})
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={exportBackendCSV}
              disabled={backendTestCases.length === 0}
              className="gap-2 text-emerald-600 border-emerald-200 hover:bg-emerald-50"
            >
              <Server className="h-4 w-4" />
              Backend ({backendTestCases.length})
            </Button>

            {truthTableEntries.length > 0 && (
              <>
                <div className="h-6 w-px bg-slate-200" />
                {/* View Mode Toggle */}
                <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
                  <Button
                    variant={viewMode === 'test_cases' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('test_cases')}
                    className="gap-2 h-7"
                  >
                    <TestTube2 className="h-3.5 w-3.5" />
                    Test Cases
                  </Button>
                  <Button
                    variant={viewMode === 'truth_table' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('truth_table')}
                    className="gap-2 h-7"
                  >
                    <ListChecks className="h-3.5 w-3.5" />
                    Truth Table ({truthTableEntries.length})
                  </Button>
                </div>
              </>
            )}
          </div>

          {/* Filter Panel */}
          {showFilters && (
            <div className="flex items-center gap-3 mt-3 pt-3 border-t border-slate-100">
              <span className="text-xs font-medium text-slate-500">Filter by:</span>
              <select
                value={filterPriority || ''}
                onChange={(e) => setFilterPriority(e.target.value || null)}
                className="text-sm px-3 py-1.5 border border-slate-200 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="">All Priorities</option>
                <option value="P0">P0 - Critical</option>
                <option value="P1">P1 - High</option>
                <option value="P2">P2 - Medium</option>
                <option value="P3">P3 - Low</option>
              </select>
              <select
                value={filterTestType || ''}
                onChange={(e) => setFilterTestType(e.target.value || null)}
                className="text-sm px-3 py-1.5 border border-slate-200 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="">All Types</option>
                {availableTestTypes.map(type => (
                  <option key={type} value={type}>{formatTestType(type)}</option>
                ))}
              </select>
              <select
                value={filterScope}
                onChange={(e) => setFilterScope(e.target.value as 'all' | 'frontend' | 'backend')}
                className="text-sm px-3 py-1.5 border border-slate-200 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="all">All Scopes</option>
                <option value="frontend">Frontend Only</option>
                <option value="backend">Backend Only</option>
              </select>
            </div>
          )}
        </div>

        {/* Breadcrumb & Stats */}
        {selectedVersion && (
          <div className="bg-white border-b border-slate-100 px-4 py-2 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-400">Viewing:</span>
              <span className="font-medium text-slate-700">{selectedFeatureName}</span>
              <ChevronRight className="h-4 w-4 text-slate-300" />
              <span className="font-medium text-blue-600">V{selectedVersion.version}</span>
              {/* Document badges in breadcrumb */}
              <div className="flex items-center gap-1 ml-2">
                {selectedVersion.documents_included.map(doc => {
                  const badge = documentBadges[doc];
                  if (!badge) return null;
                  const { Icon, color } = badge;
                  return (
                    <span
                      key={doc}
                      className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] ${color}`}
                      title={badge.label}
                    >
                      <Icon className="h-3 w-3" />
                    </span>
                  );
                })}
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-100 text-slate-600">
                <Hash className="h-3 w-3" />
                {filteredTestCases.length} total
              </span>
              <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-blue-50 text-blue-600">
                <Monitor className="h-3 w-3" />
                {frontendTestCases.length} frontend
              </span>
              <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-50 text-emerald-600">
                <Server className="h-3 w-3" />
                {backendTestCases.length} backend
              </span>
            </div>
          </div>
        )}

        {/* Test Cases Table */}
        <div className="flex-1 overflow-auto">
          {!selectedVersion ? (
            // Empty State - No Version Selected
            <div className="flex flex-col items-center justify-center h-full text-center p-8">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <FolderOpen className="h-8 w-8 text-slate-400" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 mb-2">Select a Feature Version</h3>
              <p className="text-sm text-slate-500 max-w-sm">
                Choose a feature and version from the sidebar to view test cases
              </p>
            </div>
          ) : loadingTests ? (
            // Loading State
            <div className="flex flex-col items-center justify-center h-full">
              <RefreshCw className="h-8 w-8 animate-spin text-slate-400 mb-3" />
              <span className="text-sm text-slate-500">Loading test cases...</span>
            </div>
          ) : viewMode === 'truth_table' ? (
            // Truth Table View
            loadingTruthTable ? (
              <div className="flex flex-col items-center justify-center h-full">
                <RefreshCw className="h-8 w-8 animate-spin text-slate-400 mb-3" />
                <span className="text-sm text-slate-500">Loading truth table...</span>
              </div>
            ) : truthTableEntries.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center p-8">
                <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                  <ListChecks className="h-8 w-8 text-slate-400" />
                </div>
                <h3 className="text-lg font-semibold text-slate-700 mb-2">No Truth Table Entries</h3>
                <p className="text-sm text-slate-500 max-w-sm">
                  Truth table entries are generated from navigation and state transition flows
                </p>
              </div>
            ) : (
              <div className="min-w-full overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50 sticky top-0">
                    <tr className="border-b border-slate-200">
                      <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Screen</th>
                      <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Checkpoint</th>
                      <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-20">Priority</th>
                      <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Failed → </th>
                      <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Pending → </th>
                      <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Success → </th>
                      <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-20">Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {truthTableEntries.map((entry) => {
                      const priority = priorityStyles[entry.priority] || priorityStyles.P1;
                      return (
                        <tr key={entry.id} className="hover:bg-slate-50/50 transition-colors">
                          <td className="px-3 py-3">
                            <span className="text-sm font-medium text-slate-700">{entry.screen}</span>
                          </td>
                          <td className="px-3 py-3">
                            <span className="text-sm text-slate-600">{entry.checkpoint}</span>
                          </td>
                          <td className="px-3 py-3">
                            <span className={`text-xs font-medium px-2 py-1 rounded border ${priority.bg} ${priority.text} ${priority.border}`}>
                              {entry.priority}
                            </span>
                          </td>
                          <td className="px-3 py-3">
                            <span className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded">{entry.failed_redirect}</span>
                          </td>
                          <td className="px-3 py-3">
                            <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">{entry.pending_redirect}</span>
                          </td>
                          <td className="px-3 py-3">
                            <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-1 rounded">{entry.successful_redirect}</span>
                          </td>
                          <td className="px-3 py-3">
                            <span className={`text-xs px-2 py-1 rounded ${
                              entry.result === 'Pass' ? 'bg-emerald-50 text-emerald-600' :
                              entry.result === 'Failed' ? 'bg-red-50 text-red-600' :
                              'bg-slate-100 text-slate-500'
                            }`}>
                              {entry.result}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          ) : filteredTestCases.length === 0 ? (
            // Empty State - No Test Cases
            <div className="flex flex-col items-center justify-center h-full text-center p-8">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <FileText className="h-8 w-8 text-slate-400" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 mb-2">No Test Cases Found</h3>
              <p className="text-sm text-slate-500 max-w-sm">
                {hasActiveFilters
                  ? 'Try adjusting your search or filters to find test cases'
                  : 'Generate test cases using the Test Generator to see them here'
                }
              </p>
              {hasActiveFilters && (
                <Button variant="outline" size="sm" onClick={clearFilters} className="mt-4">
                  Clear Filters
                </Button>
              )}
            </div>
          ) : (
            // Test Cases Table
            <div className="min-w-full">
              <table className="w-full">
                <thead className="bg-slate-50 sticky top-0">
                  <tr className="border-b border-slate-200">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-32">ID</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-20">Priority</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-24">Type</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Test Scenario</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">Feature</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-20">Status</th>
                    <th className="text-center px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-16">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredTestCases.map((tc) => {
                    const priority = priorityStyles[tc.priority] || priorityStyles.P2;
                    const testTypeStyle = testTypeStyles[tc.test_type?.toUpperCase()] || testTypeStyles[tc.test_type] || 'bg-slate-50 text-slate-600';

                    return (
                      <tr
                        key={tc.id}
                        className="hover:bg-slate-50/50 transition-colors cursor-pointer"
                        onClick={() => setSelectedTestCase(tc)}
                      >
                        <td className="px-4 py-3">
                          <code className="text-xs font-mono text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                            {tc.test_case_id}
                          </code>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium px-2 py-1 rounded border ${priority.bg} ${priority.text} ${priority.border}`}>
                            {tc.priority}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium px-2 py-1 rounded whitespace-nowrap ${testTypeStyle}`}>
                            {formatTestType(tc.test_type)}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <p className="text-sm text-slate-700 line-clamp-2">
                            {tc.test_scenario || tc.requirement_description}
                          </p>
                          {tc.category && (
                            <span className="text-xs text-slate-400 mt-1 inline-block">
                              <Tag className="h-3 w-3 inline mr-1" />
                              {tc.category}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-slate-600 truncate block max-w-[120px]" title={tc.feature}>
                            {tc.feature}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-1 rounded ${
                            tc.qa_status === 'Passed' ? 'bg-emerald-50 text-emerald-600' :
                            tc.qa_status === 'Failed' ? 'bg-red-50 text-red-600' :
                            tc.qa_status === 'Blocked' ? 'bg-amber-50 text-amber-600' :
                            'bg-slate-100 text-slate-500'
                          }`}>
                            {tc.qa_status || 'Pending'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-slate-400 hover:text-slate-600"
                            onClick={(e) => { e.stopPropagation(); setSelectedTestCase(tc); }}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Test Case Detail Panel */}
      {selectedTestCase && (
        <div className="w-96 bg-white border-l border-slate-200 flex flex-col overflow-hidden">
          {/* Panel Header */}
          <div className="p-4 border-b border-slate-200 flex items-center justify-between">
            <div>
              <code className="text-xs font-mono text-slate-500">{selectedTestCase.test_case_id}</code>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
                  (priorityStyles[selectedTestCase.priority] || priorityStyles.P2).bg
                } ${(priorityStyles[selectedTestCase.priority] || priorityStyles.P2).text} ${
                  (priorityStyles[selectedTestCase.priority] || priorityStyles.P2).border
                }`}>
                  {selectedTestCase.priority}
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded whitespace-nowrap ${
                  testTypeStyles[selectedTestCase.test_type?.toUpperCase()] || testTypeStyles[selectedTestCase.test_type] || 'bg-slate-50 text-slate-600'
                }`}>
                  {formatTestType(selectedTestCase.test_type)}
                </span>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedTestCase(null)}
              className="h-8 w-8 p-0"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Panel Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Test Scenario */}
            <div>
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Test Scenario</h4>
              <p className="text-sm text-slate-700 leading-relaxed">
                {selectedTestCase.test_scenario || selectedTestCase.requirement_description}
              </p>
            </div>

            {/* Category & User Type */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-50 rounded-lg p-3">
                <span className="text-xs text-slate-500 block mb-1">Category</span>
                <span className="text-sm font-medium text-slate-700">{selectedTestCase.category || 'General'}</span>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <span className="text-xs text-slate-500 block mb-1">User Type</span>
                <span className="text-sm font-medium text-slate-700">{selectedTestCase.user_type || 'Any'}</span>
              </div>
            </div>

            {/* Precondition */}
            {selectedTestCase.precondition && (
              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Precondition</h4>
                <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                  <p className="text-sm text-amber-800">{selectedTestCase.precondition}</p>
                </div>
              </div>
            )}

            {/* Steps */}
            {(selectedTestCase.steps_to_execute || selectedTestCase.test_step) && (
              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Steps to Execute</h4>
                <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                  <p className="text-sm text-blue-800 whitespace-pre-wrap">
                    {selectedTestCase.steps_to_execute || selectedTestCase.test_step}
                  </p>
                </div>
              </div>
            )}

            {/* Expected Result */}
            {selectedTestCase.expected_result && (
              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Expected Result</h4>
                <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
                  {selectedTestCase.expected_result.includes('✓') ? (
                    <ul className="text-sm text-emerald-800 space-y-1">
                      {selectedTestCase.expected_result.split('✓').filter(item => item.trim()).map((item, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-emerald-600 mt-0.5">✓</span>
                          <span>{item.trim()}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-emerald-800">{selectedTestCase.expected_result}</p>
                  )}
                </div>
              </div>
            )}

            {/* Status */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-50 rounded-lg p-3">
                <span className="text-xs text-slate-500 block mb-1">Dev Status</span>
                <span className={`text-xs font-medium px-2 py-1 rounded inline-block ${
                  selectedTestCase.dev_status === 'Done' ? 'bg-emerald-100 text-emerald-700' :
                  selectedTestCase.dev_status === 'In Progress' ? 'bg-blue-100 text-blue-700' :
                  'bg-slate-200 text-slate-600'
                }`}>
                  {selectedTestCase.dev_status || 'Not Started'}
                </span>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <span className="text-xs text-slate-500 block mb-1">QA Status</span>
                <span className={`text-xs font-medium px-2 py-1 rounded inline-block ${
                  selectedTestCase.qa_status === 'Passed' ? 'bg-emerald-100 text-emerald-700' :
                  selectedTestCase.qa_status === 'Failed' ? 'bg-red-100 text-red-700' :
                  selectedTestCase.qa_status === 'Blocked' ? 'bg-amber-100 text-amber-700' :
                  'bg-slate-200 text-slate-600'
                }`}>
                  {selectedTestCase.qa_status || 'Not Started'}
                </span>
              </div>
            </div>

            {/* Metadata */}
            <div className="pt-4 border-t border-slate-100">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Metadata</h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Feature</span>
                  <span className="text-slate-700 font-medium">{selectedTestCase.feature}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Screen</span>
                  <span className="text-slate-700">{selectedTestCase.screen_reference || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Coverage</span>
                  <span className="text-slate-700">{selectedTestCase.coverage_score}%</span>
                </div>
                {selectedTestCase.generated_at && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Generated</span>
                    <span className="text-slate-700 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(selectedTestCase.generated_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Comments */}
            {selectedTestCase.comments && (
              <div className="pt-4 border-t border-slate-100">
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Comments</h4>
                <p className="text-sm text-slate-600 italic">{selectedTestCase.comments}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
