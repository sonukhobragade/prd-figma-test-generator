import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  RefreshCw,
  Bug,
  Upload,
  AlertCircle,
  CheckCircle,
  Check,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Search,
  FileText,
  Trash2,
  AlertTriangle,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface BugsStatus {
  enabled: boolean;
  health: string;
  total_bugs: number;
  by_feature: Record<string, FeatureStats>;
  message?: string;
}

interface FeatureStats {
  total: number;
  p0: number;
  p1: number;
  p2: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  source_files: string[];
}

interface BugDocument {
  bug_id: string;
  title: string;
  description: string;
  category: string;
  priority: string;
  screen: string;
  expected: string;
  actual: string;
  dev_type: string;
  status: string;
  root_cause: string;
  comments: string;
  source_format: string;
  feature_name: string;
  source_file: string;
  uploaded_at: string;
}

interface UploadResult {
  success: boolean;
  message: string;
  feature_name?: string;
  source_file?: string;
  format_detected?: string;
  total?: number;
  p0?: number;
  p1?: number;
  p2?: number;
  by_category?: Record<string, number>;
  by_status?: Record<string, number>;
}


export function BugsKnowledge() {
  const [status, setStatus] = useState<BugsStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload state - Multi-file support
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState<Array<UploadResult & { fileName: string }>>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [fileFeatureNames, setFileFeatureNames] = useState<Record<string, string>>({});
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, 'pending' | 'uploading' | 'success' | 'error'>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Browse state
  const [expandedFeatures, setExpandedFeatures] = useState<Set<string>>(new Set());
  const [featureBugs, setFeatureBugs] = useState<Record<string, BugDocument[]>>({});
  const [loadingFeatures, setLoadingFeatures] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<BugDocument[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const FEATURES_PER_PAGE = 10;

  // Analyzer state
  const [showAnalyzer, setShowAnalyzer] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<{
    total_bugs: number;
    extracted_rules: number;
    rules: Array<{
      rule_id: string;
      rule_text: string;
      category: string;
      confidence: number;
      priority: string;
      test_suggestion: string;
    }>;
    patterns: Record<string, any[]>;
  } | null>(null);
  const [isUpdatingKnowledge, setIsUpdatingKnowledge] = useState(false);
  const [successNotification, setSuccessNotification] = useState<{
    show: boolean;
    title: string;
    message: string;
    details?: { label: string; value: string | number }[];
  } | null>(null);

  // Auto-dismiss success notification after 5 seconds
  useEffect(() => {
    if (successNotification?.show) {
      const timer = setTimeout(() => {
        setSuccessNotification(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [successNotification]);

  // Compute paginated features
  const { totalFeatures, totalPages, paginatedFeatures, startIndex, endIndex } = useMemo(() => {
    const sorted = status?.by_feature
      ? Object.entries(status.by_feature).sort(([, a], [, b]) => b.total - a.total)
      : [];
    const total = sorted.length;
    const pages = Math.ceil(total / FEATURES_PER_PAGE);
    const start = (currentPage - 1) * FEATURES_PER_PAGE;
    const end = start + FEATURES_PER_PAGE;
    const paginated = sorted.slice(start, end);

    return {
      sortedFeatures: sorted,
      totalFeatures: total,
      totalPages: pages,
      paginatedFeatures: paginated,
      startIndex: start,
      endIndex: end,
    };
  }, [status?.by_feature, currentPage, FEATURES_PER_PAGE]);

  // Reset pagination when features change
  useEffect(() => {
    setCurrentPage(1);
  }, [totalFeatures]);

  // Fetch status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/bugs/status');
      const data = await response.json();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch bugs status:', err);
      setError('Failed to connect to bugs service');
    }
  }, []);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      await fetchStatus();
      setIsLoading(false);
    };
    loadData();
  }, [fetchStatus]);

  // Search bugs
  useEffect(() => {
    const searchBugs = async () => {
      if (!searchQuery.trim()) {
        setSearchResults([]);
        return;
      }

      setIsSearching(true);
      try {
        const response = await fetch(`/api/bugs/search?q=${encodeURIComponent(searchQuery)}&top_k=20`);
        const data = await response.json();
        if (data.success) {
          setSearchResults(data.results || []);
        }
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setIsSearching(false);
      }
    };

    const timeoutId = setTimeout(searchBugs, 300);
    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  // Fetch bugs for a feature
  const fetchFeatureBugs = async (featureName: string) => {
    setLoadingFeatures((prev) => new Set(prev).add(featureName));
    try {
      const response = await fetch(`/api/bugs/list?feature_name=${encodeURIComponent(featureName)}&limit=100`);
      const data = await response.json();
      if (data.success) {
        setFeatureBugs((prev) => ({ ...prev, [featureName]: data.bugs || [] }));
      }
    } catch (err) {
      console.error('Failed to fetch feature bugs:', err);
    } finally {
      setLoadingFeatures((prev) => {
        const next = new Set(prev);
        next.delete(featureName);
        return next;
      });
    }
  };

  // Toggle feature expansion
  const toggleFeature = async (featureName: string) => {
    const isExpanded = expandedFeatures.has(featureName);

    setExpandedFeatures((prev) => {
      const next = new Set(prev);
      if (next.has(featureName)) {
        next.delete(featureName);
      } else {
        next.add(featureName);
      }
      return next;
    });

    // Fetch bugs if expanding and not cached
    if (!isExpanded && !featureBugs[featureName]) {
      await fetchFeatureBugs(featureName);
    }
  };

  // Handle multiple file selection
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      setSelectedFiles(files);
      // Initialize feature names from filenames (without .csv extension)
      const names: Record<string, string> = {};
      const progress: Record<string, 'pending' | 'uploading' | 'success' | 'error'> = {};
      files.forEach((file) => {
        const baseName = file.name.replace(/\.csv$/i, '').replace(/[_-]/g, ' ');
        names[file.name] = baseName;
        progress[file.name] = 'pending';
      });
      setFileFeatureNames(names);
      setUploadProgress(progress);
      setUploadResults([]);
    }
  };

  // Update feature name for a specific file
  const updateFeatureName = (fileName: string, name: string) => {
    setFileFeatureNames((prev) => ({ ...prev, [fileName]: name }));
  };

  // Remove a file from selection
  const removeFile = (fileName: string) => {
    setSelectedFiles((prev) => prev.filter((f) => f.name !== fileName));
    setFileFeatureNames((prev) => {
      const next = { ...prev };
      delete next[fileName];
      return next;
    });
    setUploadProgress((prev) => {
      const next = { ...prev };
      delete next[fileName];
      return next;
    });
  };

  // Upload all selected CSVs
  const handleUploadAll = async () => {
    if (selectedFiles.length === 0) {
      setError('Please select at least one CSV file');
      return;
    }

    // Check all files have feature names
    const missingNames = selectedFiles.filter((f) => !fileFeatureNames[f.name]?.trim());
    if (missingNames.length > 0) {
      setError(`Please enter feature names for: ${missingNames.map((f) => f.name).join(', ')}`);
      return;
    }

    setIsUploading(true);
    setError(null);
    const results: Array<UploadResult & { fileName: string }> = [];

    // Upload files sequentially
    for (const file of selectedFiles) {
      setUploadProgress((prev) => ({ ...prev, [file.name]: 'uploading' }));

      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('feature_name', fileFeatureNames[file.name].trim());

        const response = await fetch('/api/bugs/upload', {
          method: 'POST',
          body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
          if (data.duplicate) {
            results.push({
              ...data,
              fileName: file.name,
              success: false,
              message: `Duplicate: already uploaded as "${data.existing_feature}"`,
            });
            setUploadProgress((prev) => ({ ...prev, [file.name]: 'error' }));
          } else {
            results.push({
              fileName: file.name,
              success: false,
              message: data.detail || data.message || 'Upload failed',
            });
            setUploadProgress((prev) => ({ ...prev, [file.name]: 'error' }));
          }
        } else {
          results.push({ ...data, fileName: file.name });
          setUploadProgress((prev) => ({ ...prev, [file.name]: 'success' }));
        }
      } catch (err) {
        results.push({
          fileName: file.name,
          success: false,
          message: err instanceof Error ? err.message : 'Upload failed',
        });
        setUploadProgress((prev) => ({ ...prev, [file.name]: 'error' }));
      }
    }

    setUploadResults(results);

    // Refresh status
    await fetchStatus();

    // Check if all succeeded
    const allSucceeded = results.every((r) => r.success);
    if (allSucceeded) {
      // Reset form and close modal after short delay to show success
      setTimeout(() => {
        setSelectedFiles([]);
        setFileFeatureNames({});
        setUploadProgress({});
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        setShowUploadModal(false);
      }, 1500);
    }

    setIsUploading(false);
  };

  // Delete bugs by file
  const handleDeleteFile = async (sourceFile: string) => {
    if (!confirm(`Delete all bugs from "${sourceFile}"? This cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/bugs/file/${encodeURIComponent(sourceFile)}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Delete failed');
      }

      // Refresh status
      await fetchStatus();

      // Clear cached bugs
      setFeatureBugs({});
      setExpandedFeatures(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  // Analyze bugs for business rules
  const handleAnalyzeBugs = async () => {
    setIsAnalyzing(true);
    setError(null);

    try {
      const response = await fetch('/api/bugs/analyze');
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Analysis failed');
      }

      setAnalysisResult(data);
      setShowAnalyzer(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Update domain knowledge
  const handleUpdateKnowledge = async () => {
    setIsUpdatingKnowledge(true);
    setError(null);

    try {
      const response = await fetch('/api/bugs/domain-knowledge/update', {
        method: 'POST',
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Update failed');
      }

      setSuccessNotification({
        show: true,
        title: 'Domain Knowledge Updated!',
        message: 'Business rules extracted from bugs have been saved.',
        details: [
          { label: 'File', value: data.file_path },
          { label: 'Rules Extracted', value: data.total_rules },
          { label: 'Categories', value: data.categories.join(', ') },
        ],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed');
    } finally {
      setIsUpdatingKnowledge(false);
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  };

  // Get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'P0':
        return 'bg-red-100 text-red-700 border-red-200';
      case 'P1':
        return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'P2':
        return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'fixed':
      case 'verified':
        return 'text-green-600';
      case 'open':
        return 'text-red-600';
      default:
        return 'text-yellow-600';
    }
  };

  // Calculate max bugs for bar width
  const maxBugs = status?.by_feature
    ? Math.max(...Object.values(status.by_feature).map((f) => f.total), 1)
    : 1;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background px-6 py-4">
        <div className="max-w-full mx-auto">
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <span className="ml-3 text-muted-foreground">Loading bugs knowledge...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-6 py-4">
      {/* Success Toast Notification */}
      {successNotification?.show && (
        <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2 fade-in duration-300">
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg shadow-lg p-4 max-w-md">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 rounded-full bg-green-100 dark:bg-green-800 flex items-center justify-center">
                  <Check className="h-5 w-5 text-green-600 dark:text-green-400" />
                </div>
              </div>
              <div className="flex-1">
                <h4 className="font-semibold text-green-800 dark:text-green-200">
                  {successNotification.title}
                </h4>
                <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                  {successNotification.message}
                </p>
                {successNotification.details && (
                  <div className="mt-3 space-y-1">
                    {successNotification.details.map((detail, idx) => (
                      <div key={idx} className="flex text-xs">
                        <span className="text-green-600 dark:text-green-400 font-medium w-24">{detail.label}:</span>
                        <span className="text-green-700 dark:text-green-300 flex-1">{detail.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <button
                onClick={() => setSuccessNotification(null)}
                className="flex-shrink-0 text-green-500 hover:text-green-700 dark:hover:text-green-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-full mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
              <Bug className="h-6 w-6" style={{ color: 'hsl(var(--primary))' }} />
              Bugs Knowledge
            </h2>
            <p className="text-muted-foreground mt-1">
              Upload bug CSVs to help test generation learn from historical issues
            </p>
          </div>
          <Button
            onClick={() => setShowUploadModal(true)}
            className="gap-2"
            style={{ backgroundColor: 'hsl(var(--primary))' }}
          >
            <Upload className="h-4 w-4" />
            Upload CSV
          </Button>
        </div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Bugs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Bug className="h-5 w-5" style={{ color: 'hsl(var(--primary))' }} />
                <span className="text-2xl font-bold">{status?.total_bugs || 0}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Features</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-blue-500" />
                <span className="text-2xl font-bold">
                  {status?.by_feature ? Object.keys(status.by_feature).length : 0}
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">P0 Critical</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                <span className="text-2xl font-bold text-red-600">
                  {status?.by_feature
                    ? Object.values(status.by_feature).reduce((sum, f) => sum + f.p0, 0)
                    : 0}
                </span>
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

        {/* Error Display */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-red-800">Error</p>
                  <p className="text-sm text-red-600 mt-1">{error}</p>
                </div>
                <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800">
                  <X className="h-4 w-4" />
                </button>
              </div>
            </CardContent>
          </Card>
        )}


        {/* Search */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Search Bugs
            </CardTitle>
            <CardDescription>Search for bugs by keyword, feature, or description</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search bugs (e.g., subscription, navigation, wallet)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm"
              />
              {isSearching && (
                <RefreshCw className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>

            {/* Search Results */}
            {searchQuery && searchResults.length > 0 && (
              <div className="mt-4 space-y-2 max-h-96 overflow-y-auto">
                {searchResults.map((bug, index) => (
                  <div key={index} className="border rounded-lg p-3 hover:bg-muted/50">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{bug.title}</p>
                        <div className="flex flex-wrap gap-1 mt-1">
                          <span className={`px-1.5 py-0.5 text-xs rounded ${getPriorityColor(bug.priority)}`}>
                            {bug.priority}
                          </span>
                          <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">
                            {bug.category}
                          </span>
                          <span className="px-1.5 py-0.5 text-xs bg-gray-100 text-gray-700 rounded">
                            {bug.feature_name}
                          </span>
                        </div>
                      </div>
                      <span className={`text-xs font-medium ${getStatusColor(bug.status)}`}>{bug.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {searchQuery && searchResults.length === 0 && !isSearching && (
              <div className="mt-4 text-center py-8 text-muted-foreground">
                <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No bugs found matching "{searchQuery}"</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Business Rules Analyzer */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5" />
                  Learn from Bugs
                </CardTitle>
                <CardDescription>
                  Extract business rules and update domain knowledge from bug patterns
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAnalyzeBugs}
                  disabled={isAnalyzing || !status?.total_bugs}
                >
                  {isAnalyzing ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Search className="h-4 w-4 mr-2" />
                      Analyze Bugs
                    </>
                  )}
                </Button>
                <Button
                  variant={analysisResult ? "default" : "outline"}
                  size="sm"
                  onClick={handleUpdateKnowledge}
                  disabled={isUpdatingKnowledge || !analysisResult}
                  style={{ backgroundColor: analysisResult ? 'hsl(var(--primary))' : undefined }}
                >
                  {isUpdatingKnowledge ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Updating...
                    </>
                  ) : (
                    <>
                      <FileText className="h-4 w-4 mr-2" />
                      Update Domain Knowledge
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardHeader>
          {analysisResult && (
            <CardContent>
              {/* Analysis Summary */}
              <div className="grid grid-cols-4 gap-4 mb-4">
                <div className="bg-muted/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold">{analysisResult.total_bugs}</p>
                  <p className="text-xs text-muted-foreground">Bugs Analyzed</p>
                </div>
                <div className="bg-muted/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold">{analysisResult.extracted_rules}</p>
                  <p className="text-xs text-muted-foreground">Rules Extracted</p>
                </div>
                <div className="bg-muted/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold">
                    {Object.keys(analysisResult.patterns || {}).length}
                  </p>
                  <p className="text-xs text-muted-foreground">Patterns Found</p>
                </div>
                <div className="bg-muted/50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold">
                    {new Set(analysisResult.rules?.map((r) => r.category) || []).size}
                  </p>
                  <p className="text-xs text-muted-foreground">Categories</p>
                </div>
              </div>

              {/* Extracted Rules */}
              {analysisResult.rules && analysisResult.rules.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-medium text-sm">Extracted Business Rules</h4>
                    <button
                      onClick={() => setShowAnalyzer(!showAnalyzer)}
                      className="text-xs text-primary hover:underline"
                    >
                      {showAnalyzer ? 'Hide Details' : 'Show Details'}
                    </button>
                  </div>

                  {showAnalyzer && (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {analysisResult.rules.slice(0, 15).map((rule, idx) => (
                        <div
                          key={idx}
                          className="border rounded-lg p-3 bg-muted/30"
                        >
                          <div className="flex items-start gap-2">
                            <span className={`px-1.5 py-0.5 text-xs rounded flex-shrink-0 ${getPriorityColor(rule.priority)}`}>
                              {rule.priority}
                            </span>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium">{rule.rule_text.slice(0, 150)}...</p>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                                  {rule.category}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  Confidence: {Math.round(rule.confidence * 100)}%
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1 italic">
                                💡 {rule.test_suggestion.slice(0, 100)}...
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          )}
        </Card>

        {/* Bug Distribution by Feature */}
        {totalFeatures > 0 && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Bug Distribution by Feature
                  </CardTitle>
                  <CardDescription>Click a feature to see detailed bugs</CardDescription>
                </div>
                {totalPages > 1 && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>
                      {startIndex + 1}-{Math.min(endIndex, totalFeatures)} of {totalFeatures}
                    </span>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {paginatedFeatures.map(([featureName, stats]) => {
                    const isExpanded = expandedFeatures.has(featureName);
                    const isLoadingBugs = loadingFeatures.has(featureName);
                    const bugs = featureBugs[featureName] || [];
                    const barWidth = (stats.total / maxBugs) * 100;

                    return (
                      <div key={featureName} className="border rounded-lg overflow-hidden">
                        {/* Feature Header */}
                        <div
                          className="p-4 cursor-pointer hover:bg-muted/50 transition-colors"
                          onClick={() => toggleFeature(featureName)}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-3">
                              <span className="font-medium">{featureName}</span>
                              <span className="text-sm text-muted-foreground">
                                {stats.total} bugs
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              {stats.p0 > 0 && (
                                <span className="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded font-medium">
                                  P0: {stats.p0}
                                </span>
                              )}
                              {stats.p1 > 0 && (
                                <span className="px-2 py-0.5 text-xs bg-orange-100 text-orange-700 rounded font-medium">
                                  P1: {stats.p1}
                                </span>
                              )}
                              {isLoadingBugs ? (
                                <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
                              ) : isExpanded ? (
                                <ChevronUp className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              )}
                            </div>
                          </div>

                          {/* Progress bar */}
                          <div className="h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-300"
                              style={{
                                width: `${barWidth}%`,
                                backgroundColor: stats.p0 > 5 ? '#ef4444' : stats.p0 > 0 ? '#f97316' : 'hsl(var(--primary))',
                              }}
                            />
                          </div>

                          {/* Source files */}
                          {stats.source_files.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {stats.source_files.map((file, i) => (
                                <span key={i} className="text-xs text-muted-foreground font-mono">
                                  {file}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Expanded Bug List */}
                        {isExpanded && (
                          <div className="border-t bg-muted/30 p-4">
                            {isLoadingBugs ? (
                              <div className="flex items-center justify-center py-8">
                                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                                <span className="ml-2 text-muted-foreground">Loading bugs...</span>
                              </div>
                            ) : bugs.length === 0 ? (
                              <div className="text-center py-8 text-muted-foreground">
                                <Bug className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                <p>No bugs found</p>
                              </div>
                            ) : (
                              <div className="space-y-2 max-h-96 overflow-y-auto">
                                {bugs.map((bug, index) => (
                                  <div
                                    key={index}
                                    className="bg-background border rounded-lg p-3 hover:shadow-sm transition-shadow"
                                  >
                                    <div className="flex items-start justify-between gap-2">
                                      <div className="flex-1 min-w-0">
                                        <p className="font-medium text-sm">{bug.title}</p>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                          <span
                                            className={`px-1.5 py-0.5 text-xs rounded border ${getPriorityColor(
                                              bug.priority
                                            )}`}
                                          >
                                            {bug.priority}
                                          </span>
                                          <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">
                                            {bug.category}
                                          </span>
                                          {bug.screen && (
                                            <span className="px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
                                              {bug.screen}
                                            </span>
                                          )}
                                          <span className="px-1.5 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                                            {bug.dev_type}
                                          </span>
                                        </div>
                                        {bug.expected && (
                                          <p className="text-xs text-muted-foreground mt-2">
                                            <span className="font-medium">Expected:</span> {bug.expected}
                                          </p>
                                        )}
                                        {bug.actual && (
                                          <p className="text-xs text-muted-foreground">
                                            <span className="font-medium">Actual:</span> {bug.actual}
                                          </p>
                                        )}
                                      </div>
                                      <div className="text-right flex-shrink-0">
                                        <span className={`text-xs font-medium ${getStatusColor(bug.status)}`}>
                                          {bug.status}
                                        </span>
                                        <p className="text-xs text-muted-foreground mt-1">
                                          {formatDate(bug.uploaded_at)}
                                        </p>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Delete option */}
                            {stats.source_files.length > 0 && (
                              <div className="mt-4 pt-4 border-t">
                                <p className="text-xs text-muted-foreground mb-2">Delete bugs from:</p>
                                <div className="flex flex-wrap gap-2">
                                  {stats.source_files.map((file, i) => (
                                    <button
                                      key={i}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteFile(file);
                                      }}
                                      className="flex items-center gap-1 px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded border border-red-200"
                                    >
                                      <Trash2 className="h-3 w-3" />
                                      {file}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-6 pt-4 border-t">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    className="gap-1"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>

                  <div className="flex items-center gap-1">
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
                      // Show first page, last page, current page, and 1 page on each side of current
                      const showPage =
                        page === 1 ||
                        page === totalPages ||
                        Math.abs(page - currentPage) <= 1;

                      // Show ellipsis
                      const showLeftEllipsis = page === 2 && currentPage > 3;
                      const showRightEllipsis = page === totalPages - 1 && currentPage < totalPages - 2;

                      if (showLeftEllipsis || showRightEllipsis) {
                        if ((showLeftEllipsis && page === 2) || (showRightEllipsis && page === totalPages - 1)) {
                          return (
                            <span key={page} className="px-2 text-muted-foreground">
                              ...
                            </span>
                          );
                        }
                        return null;
                      }

                      if (!showPage) return null;

                      return (
                        <button
                          key={page}
                          onClick={() => setCurrentPage(page)}
                          className={`w-8 h-8 rounded text-sm font-medium transition-colors ${
                            page === currentPage
                              ? 'bg-primary text-primary-foreground'
                              : 'hover:bg-muted text-muted-foreground'
                          }`}
                          style={page === currentPage ? { backgroundColor: 'hsl(var(--primary))' } : {}}
                        >
                          {page}
                        </button>
                      );
                    })}
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                    className="gap-1"
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Empty State */}
        {totalFeatures === 0 && (
          <Card>
            <CardContent className="py-12">
              <div className="text-center">
                <Bug className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                <h3 className="text-lg font-medium mb-2">No Bugs Uploaded Yet</h3>
                <p className="text-muted-foreground mb-4">
                  Upload your bug CSVs to help the test generator learn from historical issues.
                </p>
                <Button onClick={() => setShowUploadModal(true)} style={{ backgroundColor: 'hsl(var(--primary))' }}>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload Your First CSV
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Upload Modal - Multi-file Support */}
        {showUploadModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <Card className="w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Upload className="h-5 w-5" />
                    Upload Bugs CSVs
                  </CardTitle>
                  <button
                    onClick={() => {
                      setShowUploadModal(false);
                      setSelectedFiles([]);
                      setFileFeatureNames({});
                      setUploadProgress({});
                      setUploadResults([]);
                      setError(null);
                    }}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <CardDescription>
                  Upload multiple bug CSVs at once. Feature names are auto-generated from filenames.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 overflow-y-auto flex-1">
                {/* File Upload Zone */}
                <div>
                  <label className="block text-sm font-medium mb-1">
                    CSV Files <span className="text-red-500">*</span>
                  </label>
                  <div
                    className="border-2 border-dashed rounded-lg p-6 text-center hover:border-primary/50 transition-colors cursor-pointer"
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const files = Array.from(e.dataTransfer.files).filter((f) => f.name.endsWith('.csv'));
                      if (files.length > 0) {
                        const names: Record<string, string> = { ...fileFeatureNames };
                        const progress: Record<string, 'pending' | 'uploading' | 'success' | 'error'> = { ...uploadProgress };
                        files.forEach((file) => {
                          if (!names[file.name]) {
                            const baseName = file.name.replace(/\.csv$/i, '').replace(/[_-]/g, ' ');
                            names[file.name] = baseName;
                            progress[file.name] = 'pending';
                          }
                        });
                        setSelectedFiles((prev) => [...prev, ...files.filter((f) => !prev.find((p) => p.name === f.name))]);
                        setFileFeatureNames(names);
                        setUploadProgress(progress);
                      }
                    }}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".csv"
                      multiple
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                    <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Drag & drop CSV files here or click to browse
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      You can select multiple files at once
                    </p>
                  </div>
                </div>

                {/* Selected Files List */}
                {selectedFiles.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">
                        Selected Files ({selectedFiles.length})
                      </label>
                      <button
                        onClick={() => {
                          setSelectedFiles([]);
                          setFileFeatureNames({});
                          setUploadProgress({});
                          if (fileInputRef.current) {
                            fileInputRef.current.value = '';
                          }
                        }}
                        className="text-xs text-red-600 hover:text-red-700"
                      >
                        Clear All
                      </button>
                    </div>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {selectedFiles.map((file) => (
                        <div
                          key={file.name}
                          className={`border rounded-lg p-3 ${
                            uploadProgress[file.name] === 'success'
                              ? 'bg-green-50 border-green-200'
                              : uploadProgress[file.name] === 'error'
                              ? 'bg-red-50 border-red-200'
                              : uploadProgress[file.name] === 'uploading'
                              ? 'bg-blue-50 border-blue-200'
                              : 'bg-background'
                          }`}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <FileText className="h-4 w-4 flex-shrink-0" style={{ color: 'hsl(var(--primary))' }} />
                            <span className="text-sm font-medium truncate flex-1">{file.name}</span>
                            {uploadProgress[file.name] === 'success' && (
                              <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
                            )}
                            {uploadProgress[file.name] === 'error' && (
                              <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
                            )}
                            {uploadProgress[file.name] === 'uploading' && (
                              <RefreshCw className="h-4 w-4 text-blue-600 animate-spin flex-shrink-0" />
                            )}
                            {uploadProgress[file.name] === 'pending' && (
                              <button
                                onClick={() => removeFile(file.name)}
                                className="text-muted-foreground hover:text-red-600 flex-shrink-0"
                              >
                                <X className="h-4 w-4" />
                              </button>
                            )}
                          </div>
                          <input
                            type="text"
                            placeholder="Feature name"
                            value={fileFeatureNames[file.name] || ''}
                            onChange={(e) => updateFeatureName(file.name, e.target.value)}
                            disabled={uploadProgress[file.name] !== 'pending'}
                            className="w-full px-2 py-1.5 text-sm border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary/50 disabled:opacity-50"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Upload Results */}
                {uploadResults.length > 0 && (
                  <div className="bg-muted/50 rounded-lg p-4">
                    <p className="font-medium mb-2">Upload Results:</p>
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                      {uploadResults.map((result, i) => (
                        <div
                          key={i}
                          className={`text-sm p-2 rounded ${
                            result.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}
                        >
                          <span className="font-medium">{result.fileName}:</span>{' '}
                          {result.success
                            ? `${result.total} bugs indexed (P0: ${result.p0 || 0}, P1: ${result.p1 || 0})`
                            : result.message}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 pt-2">
                  <Button
                    onClick={handleUploadAll}
                    disabled={selectedFiles.length === 0 || isUploading}
                    className="flex-1"
                    style={{ backgroundColor: 'hsl(var(--primary))' }}
                  >
                    {isUploading ? (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        Uploading ({Object.values(uploadProgress).filter((s) => s === 'success').length}/{selectedFiles.length})
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4 mr-2" />
                        Upload All ({selectedFiles.length} files)
                      </>
                    )}
                  </Button>
                </div>

                {/* Format Info */}
                <div className="text-xs text-muted-foreground">
                  <p className="font-medium mb-1">Supported formats:</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    <li>Frontend Bugs (Bugs, Dev, Priority, Dev Status...)</li>
                    <li>UI/Visual Bugs (#, Bugs, Priority...)</li>
                    <li>API/Backend (Test Suite, TC, Test Description...)</li>
                    <li>Navigation Truth Table (Screen, CheckPoint...)</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
