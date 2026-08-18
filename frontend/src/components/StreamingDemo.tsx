import { useState, useEffect } from 'react';
import { useStreamingAnalysis } from '../hooks/useStreamingAnalysis';
import { FormattedMessage } from '../utils/messageFormatter';
import {
  FileText,
  Link as LinkIcon,
  Lightbulb,
  ClipboardList,
  CheckCircle2,
  Target,
  TrendingUp,
  Download,
  Calendar,
  FileCheck,
  Network,
  Table,
  BookOpen,
  PlayCircle,
  CheckCircle,
  Info,
  AlertCircle,
  ListChecks,
  AlertTriangle,
  Loader2,
  Sparkles,
  Server,
  Database,
  Monitor,
  Palette,
  Image,
  Smartphone,
  Settings,
  type LucideIcon,
} from 'lucide-react';

// Document badge mapping with SVG icons
const docBadges: Record<string, { Icon: LucideIcon; color: string }> = {
  prd: { Icon: FileText, color: 'text-blue-600' },
  figma: { Icon: Palette, color: 'text-purple-600' },
  screenshot: { Icon: Image, color: 'text-pink-600' },
  frontend_lld: { Icon: Smartphone, color: 'text-green-600' },
  backend_lld: { Icon: Settings, color: 'text-orange-600' },
};
import { FileUploadZone } from './FileUploadZone';
import { CoverageInsights } from './CoverageInsights';
import { TestCaseMindmap } from './TestCaseMindmap';
import { TestCaseDetailView } from './TestCaseDetailView';
import { CodebaseRAGStatus } from './CodebaseRAGStatus';
import { FeatureDropdown, type Feature } from './FeatureDropdown';
import { TruthTableView } from './TruthTableView';
import { BackendTestCaseTable, type BackendTestCase } from './BackendTestCaseTable';
import { LLDDocumentInput } from './LLDDocumentInput';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// Feature type is imported from FeatureDropdown

export function StreamingDemo() {
  // Input state
  const [featureName, setFeatureName] = useState('');
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null);
  const [inputMode, setInputMode] = useState<'file' | 'text' | 'figma' | 'screenshot' | 'backend-lld' | 'frontend-lld'>('file');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [screenshotFile, setScreenshotFile] = useState<File | null>(null);
  const [prdText, setPrdText] = useState('');
  const [figmaUrl, setFigmaUrl] = useState('');
  const [hasInteracted, setHasInteracted] = useState(false);
  const [savingToFeature, setSavingToFeature] = useState(false);

  // LLD Document state (Optional documents for more comprehensive test generation)
  const [backendDocFile, setBackendDocFile] = useState<File | null>(null);
  const [backendDocText, setBackendDocText] = useState('');
  const [frontendDocFile, setFrontendDocFile] = useState<File | null>(null);
  const [frontendDocText, setFrontendDocText] = useState('');

  // Flag to track if Frontend analysis should run after Backend completes
  const [pendingFrontendAnalysis, setPendingFrontendAnalysis] = useState(false);

  // LLM Provider state (API key is read from .env on the backend)
  const [llmProvider, setLlmProvider] = useState<'anthropic' | 'openai'>('openai');

  // VERSION TRACKING STATE
  const [selectedVersionNumber, setSelectedVersionNumber] = useState<number>(1);
  const [updateExistingVersion, setUpdateExistingVersion] = useState<boolean>(false);
  const [existingVersions, setExistingVersions] = useState<Array<{
    version: number;
    session_id: string;
    documents_included: string[];
    frontend_count: number;
    backend_count: number;
    last_updated: string;
  }>>([]);

  // View mode for test visualization
  const [viewMode, setViewMode] = useState<'mindmap' | 'table' | 'detailed' | 'truth_table'>('table');
  const [checklistMarkdown, setChecklistMarkdown] = useState<string>('');
  
  // Filter state
  const [selectedPriorities, setSelectedPriorities] = useState<Set<string>>(new Set(['P0', 'P1', 'P2']));
  const [selectedTestTypes, setSelectedTestTypes] = useState<Set<string>>(new Set());

  // Available test type options (Backend/Frontend)
  const testTypeOptions = [
    { value: 'backend', label: 'Backend', icon: Database },
    { value: 'frontend', label: 'Frontend', icon: Monitor },
  ];

  const {
    statusMessage,
    progress,
    testCases,
    truthTableEntries,
    completionInfo,
    error,
    startAnalysis,
    startBackendAnalysis,
    reset,
    isStreaming,
    isComplete,
    // Backend-specific state
    testScope,
    backendTestCases,
    backendChecklistInfo: _backendChecklistInfo,  // Reserved for future use
    backendCompletionInfo,
  } = useStreamingAnalysis();

  // Auto-trigger Frontend analysis after Backend completes (when both LLDs provided)
  useEffect(() => {
    if (pendingFrontendAnalysis && isComplete && testScope === 'backend' && !error) {
      // Backend completed successfully, now run Frontend (50-100% of progress)
      setPendingFrontendAnalysis(false);

      // Small delay to let user see Backend results before starting Frontend
      setTimeout(() => {
        startAnalysis(
          selectedFile || screenshotFile || null,
          featureName,
          '',
          figmaUrl.trim() || undefined,
          prdText.trim() || undefined,
          llmProvider,
          undefined,
          frontendDocFile || null,
          frontendDocText || undefined,
          selectedVersionNumber,
          updateExistingVersion,
          50,   // progressOffset: Frontend starts at 50%
          0.5   // progressScale: Frontend takes 50-100% of total progress
        );
      }, 1500);
    }
  }, [isComplete, pendingFrontendAnalysis, testScope, error, selectedVersionNumber, updateExistingVersion]);

  // Handle feature selection - auto-populate feature name and fetch versions
  const handleFeatureSelect = async (feature: Feature | null) => {
    setSelectedFeature(feature);
    if (feature) {
      setFeatureName(feature.name);
      // Fetch existing versions for this feature
      try {
        const response = await fetch(`/api/rag/features/${encodeURIComponent(feature.name)}/versions`);
        const data = await response.json();
        if (data.success && data.versions) {
          setExistingVersions(data.versions);
          // Auto-select the latest version + 1 for new tests
          const latestVersion = data.versions.length > 0
            ? Math.max(...data.versions.map((v: { version: number }) => v.version))
            : 0;
          setSelectedVersionNumber(latestVersion + 1);
          setUpdateExistingVersion(false);
        } else {
          setExistingVersions([]);
          setSelectedVersionNumber(1);
        }
      } catch (err) {
        console.error('Failed to fetch versions:', err);
        setExistingVersions([]);
        setSelectedVersionNumber(1);
      }
    } else {
      setExistingVersions([]);
      setSelectedVersionNumber(1);
      setUpdateExistingVersion(false);
    }
  };

  // Save document to feature (PRD or Figma)
  const saveDocumentToFeature = async () => {
    if (!selectedFeature) return;

    setSavingToFeature(true);
    try {
      // Save PRD if file is selected
      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);

        const response = await fetch(`/api/features/${selectedFeature.id}/prd`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          console.error('Failed to save PRD to feature');
        }
      }

      // Save Figma if URL is provided
      if (figmaUrl.trim()) {
        const formData = new FormData();
        formData.append('figma_url', figmaUrl.trim());

        const response = await fetch(`/api/features/${selectedFeature.id}/figma`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          console.error('Failed to save Figma to feature');
        }
      }
    } catch (error) {
      console.error('Error saving to feature:', error);
    } finally {
      setSavingToFeature(false);
    }
  };

  const handleStartAnalysis = async () => {
    if (!featureName.trim()) {
      alert('Please enter a feature name');
      return;
    }

    // Check if ANY input exists (regardless of active tab)
    if (!selectedFile && !prdText.trim() && !figmaUrl.trim() && !screenshotFile) {
      alert('Please provide a PRD file, text, screenshot, or Figma URL');
      return;
    }

    // If a feature is selected, save documents to it first
    if (selectedFeature) {
      await saveDocumentToFeature();
    }

    // Auto-detect what to generate based on LLD documents provided
    const hasBackendLLD = backendDocFile || backendDocText.trim();
    const hasFrontendLLD = frontendDocFile || frontendDocText.trim();

    if (hasBackendLLD && hasFrontendLLD) {
      // Both LLDs provided - Generate Backend first (0-50%), then Frontend (50-100%)
      setPendingFrontendAnalysis(true);
      startBackendAnalysis(
        selectedFile || null,
        featureName,
        llmProvider,
        undefined,
        prdText.trim() || undefined,
        backendDocFile || null,
        backendDocText || undefined,
        selectedVersionNumber,
        updateExistingVersion,
        0,    // progressOffset: Backend starts at 0%
        0.5   // progressScale: Backend takes 0-50% of total progress
      );
    } else if (hasBackendLLD) {
      // Only Backend LLD provided - Generate Backend tests
      startBackendAnalysis(
        selectedFile || null,
        featureName,
        llmProvider,
        undefined,
        prdText.trim() || undefined,
        backendDocFile || null,
        backendDocText || undefined,
        selectedVersionNumber,
        updateExistingVersion
      );
    } else {
      // Frontend LLD provided OR no LLD (default to frontend)
      startAnalysis(
        selectedFile || screenshotFile || null,
        featureName,
        '',
        figmaUrl.trim() || undefined,
        prdText.trim() || undefined,
        llmProvider,
        undefined,
        frontendDocFile || null,
        frontendDocText || undefined,
        selectedVersionNumber,
        updateExistingVersion
      );
    }
  };

  // Update validation: enable button if feature name and any input is provided
  const hasValidInput = selectedFile || prdText.trim() || figmaUrl.trim() || screenshotFile;
  const canAnalyze = featureName.trim() && hasValidInput;

  // Fetch checklist markdown when completion info is available
  useEffect(() => {
    if (completionInfo?.checklist_path) {
      // Ensure path starts with /
      const path = completionInfo.checklist_path.startsWith('/')
        ? completionInfo.checklist_path
        : `/${completionInfo.checklist_path}`;

      console.log('📥 Fetching checklist markdown from:', `http://localhost:8000${path}`);

      fetch(`http://localhost:8000${path}`)
        .then(res => {
          console.log('📥 Checklist response status:', res.status);
          return res.text();
        })
        .then(markdown => {
          console.log('📥 Checklist markdown loaded:', { length: markdown.length, preview: markdown.substring(0, 200) });
          setChecklistMarkdown(markdown);
        })
        .catch(err => console.error('❌ Failed to load checklist:', err));
    }
  }, [completionInfo]);

  return (
    <div className="min-h-screen bg-background">
      <div className="w-full mx-auto px-2 sm:px-3 lg:px-4 py-3 lg:py-4">
        {/* Hero Section - Compact */}
        <div className="mb-4 flex flex-col items-center justify-center text-center space-y-2 max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20">
            <Sparkles className="h-3.5 w-3.5" style={{ color: "hsl(var(--primary))" }} />
            <span className="text-xs font-semibold" style={{ color: "hsl(var(--primary))" }}>
              AI-Powered Test Generation
            </span>
          </div>
          <h2 className="text-2xl md:text-3xl lg:text-4xl font-bold text-foreground leading-tight text-center w-full whitespace-nowrap">
            Intelligent Test{" "}
            <span
              style={{
                background: "linear-gradient(to right, hsl(var(--primary)), hsl(var(--primary) / 0.8))",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text"
              }}
            >Generation</span>
          </h2>
          <p className="text-sm md:text-base text-muted-foreground max-w-xl mx-auto text-center">
            From PRD to test cases in seconds. AI-powered QA automation for modern development teams.
          </p>
        </div>

        {/* Codebase RAG Status - React Native Code Knowledge */}
        <div className="mb-4 max-w-4xl mx-auto">
          <CodebaseRAGStatus />
        </div>

        {/* Main Input Form - Full Width Enhanced Design */}
        <Card className="rounded-2xl shadow-xl border border-border p-4 md:p-6 lg:p-8 mb-6 bg-card w-full">
          <div className="flex items-center mb-4 pb-3 border-b border-border">
            <div 
              className="flex items-center justify-center w-10 h-10 md:w-12 md:h-12 rounded-xl shadow-md mr-3 flex-shrink-0"
              style={{ backgroundColor: "hsl(var(--primary))" }}
            >
              <FileText className="h-5 w-5 md:h-6 md:w-6 text-primary-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-lg md:text-xl lg:text-2xl font-bold text-foreground mb-0.5">Analyze Feature</h3>
              <p className="text-xs text-muted-foreground">Watch your test cases generate in real-time with AI</p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Feature Name - Combobox for new or existing feature */}
            <div className="relative z-20">
              <label className="block text-sm font-medium text-foreground mb-2">
                Feature Name <span className="text-red-500">*</span>
              </label>
              <FeatureDropdown
                value={featureName}
                onChange={(value) => {
                  setFeatureName(value);
                  setHasInteracted(true);
                }}
                selectedFeature={selectedFeature}
                onSelectFeature={handleFeatureSelect}
                placeholder="Type new feature or select existing..."
                disabled={isStreaming}
              />
              {!featureName.trim() && hasValidInput && hasInteracted && (
                <p className="mt-1 text-sm text-red-600 flex items-center gap-1">
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  Feature name is required
                </p>
              )}
            </div>

            {/* Version Selection - shows when feature is selected or new feature name entered */}
            {(featureName.trim() || selectedFeature) && (
              <div className="p-4 rounded-lg border border-border bg-muted/30">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">Version</span>
                    <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
                      V{selectedVersionNumber}
                    </span>
                  </div>
                </div>

                {existingVersions.length > 0 ? (
                  <div className="space-y-3">
                    {/* Existing Versions */}
                    <div className="text-xs text-muted-foreground mb-2">
                      Existing versions:
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {existingVersions.map((v) => (
                        <button
                          key={v.session_id}
                          onClick={() => {
                            setSelectedVersionNumber(v.version);
                            setUpdateExistingVersion(true);
                          }}
                          disabled={isStreaming}
                          className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all ${
                            selectedVersionNumber === v.version && updateExistingVersion
                              ? 'border-primary bg-primary/10 text-primary'
                              : 'border-border hover:border-primary/50 text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          <span className="font-semibold">V{v.version}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-600">
                            {v.frontend_count} FE
                          </span>
                          {v.backend_count > 0 && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-600">
                              {v.backend_count} BE
                            </span>
                          )}
                          <div className="flex gap-0.5">
                            {v.documents_included.map(doc => {
                              const badge = docBadges[doc];
                              if (!badge) return null;
                              const { Icon, color } = badge;
                              return (
                                <span key={doc} title={doc}>
                                  <Icon className={`h-3 w-3 ${color}`} />
                                </span>
                              );
                            })}
                          </div>
                        </button>
                      ))}
                      {/* New Version Button */}
                      <button
                        onClick={() => {
                          const maxVersion = Math.max(...existingVersions.map(v => v.version), 0);
                          setSelectedVersionNumber(maxVersion + 1);
                          setUpdateExistingVersion(false);
                        }}
                        disabled={isStreaming}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-all ${
                          !updateExistingVersion
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-dashed border-border hover:border-primary/50 text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        <span className="font-semibold">+ New V{Math.max(...existingVersions.map(v => v.version), 0) + 1}</span>
                      </button>
                    </div>

                    {/* Update Mode Toggle */}
                    {updateExistingVersion && (
                      <div className="mt-3 p-2 rounded-md bg-amber-50 border border-amber-200">
                        <p className="text-xs text-amber-700">
                          <strong>Update Mode:</strong> New tests will be added to V{selectedVersionNumber}.
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    This will create <strong>V1</strong> for "{featureName || 'this feature'}"
                  </p>
                )}
              </div>
            )}

            {/* LLM Provider Selection */}
            <div className="relative z-10">
              <label className="block text-sm font-medium text-foreground mb-2">
                AI Provider
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setLlmProvider('openai')}
                  disabled={isStreaming}
                  className="flex-1 px-4 py-2 rounded-lg border text-sm font-medium transition-all"
                  style={{
                    borderColor: llmProvider === 'openai' ? 'hsl(var(--primary))' : 'hsl(var(--border))',
                    backgroundColor: llmProvider === 'openai' ? 'hsl(var(--primary) / 0.1)' : 'hsl(var(--background))',
                    color: llmProvider === 'openai' ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))'
                  }}
                >
                  OpenAI (GPT-4 Turbo)
                </button>
                <button
                  type="button"
                  onClick={() => setLlmProvider('anthropic')}
                  disabled={isStreaming}
                  className="flex-1 px-4 py-2 rounded-lg border text-sm font-medium transition-all"
                  style={{
                    borderColor: llmProvider === 'anthropic' ? 'hsl(var(--primary))' : 'hsl(var(--border))',
                    backgroundColor: llmProvider === 'anthropic' ? 'hsl(var(--primary) / 0.1)' : 'hsl(var(--background))',
                    color: llmProvider === 'anthropic' ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))'
                  }}
                >
                  Anthropic (Claude)
                </button>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Uses API key from .env file ({llmProvider === 'openai' ? 'OPENAI_API_KEY' : 'ANTHROPIC_API_KEY'})
              </p>
            </div>

            {/* Section Label */}
            <div className="flex items-center gap-3 mb-1">
              <span className="text-sm font-medium text-foreground">Input Sources</span>
              <div className="flex-1 h-px bg-border/50" />
            </div>

            {/* Input Method Tabs */}
            <div className="flex gap-2 p-1 bg-muted/50 rounded-xl border border-border/50 overflow-x-auto">
              <Button
                onClick={() => setInputMode('file')}
                disabled={isStreaming}
                variant={inputMode === 'file' ? 'default' : 'ghost'}
                className={`flex items-center px-4 py-2 font-medium text-sm rounded-lg transition-all whitespace-nowrap ${
                  inputMode === 'file'
                    ? 'shadow-md'
                    : 'hover:bg-muted'
                }`}
              >
                <FileText className="h-4 w-4 mr-2" />
                PRD Upload {selectedFile && <span className="ml-1 text-xs">✓</span>}
              </Button>
              <Button
                onClick={() => setInputMode('text')}
                disabled={isStreaming}
                variant={inputMode === 'text' ? 'default' : 'ghost'}
                className={`flex items-center px-4 py-2 font-medium text-sm rounded-lg transition-all whitespace-nowrap ${
                  inputMode === 'text'
                    ? 'shadow-md'
                    : 'hover:bg-muted'
                }`}
              >
                <FileText className="h-4 w-4 mr-2" />
                Additional Info {prdText.trim() && <span className="ml-1 text-xs">✓</span>}
              </Button>
              <Button
                onClick={() => setInputMode('figma')}
                disabled={isStreaming}
                variant={inputMode === 'figma' ? 'default' : 'ghost'}
                className={`flex items-center px-4 py-2 font-medium text-sm rounded-lg transition-all whitespace-nowrap ${
                  inputMode === 'figma'
                    ? 'shadow-md'
                    : 'hover:bg-muted'
                }`}
              >
                <LinkIcon className="h-4 w-4 mr-2" />
                Figma URL {figmaUrl.trim() && <span className="ml-1 text-xs">✓</span>}
              </Button>
              <Button
                onClick={() => setInputMode('screenshot')}
                disabled={isStreaming}
                variant={inputMode === 'screenshot' ? 'default' : 'ghost'}
                className={`flex items-center px-4 py-2 font-medium text-sm rounded-lg transition-all whitespace-nowrap ${
                  inputMode === 'screenshot'
                    ? 'shadow-md'
                    : 'hover:bg-muted'
                }`}
              >
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Figma Screen {screenshotFile && <span className="ml-1 text-xs">✓</span>}
              </Button>
              <Button
                onClick={() => setInputMode('backend-lld')}
                disabled={isStreaming}
                variant={inputMode === 'backend-lld' ? 'default' : 'ghost'}
                className={`flex items-center px-4 py-2 font-medium text-sm rounded-lg transition-all whitespace-nowrap ${
                  inputMode === 'backend-lld'
                    ? 'shadow-md'
                    : 'hover:bg-muted'
                }`}
              >
                <Server className="h-4 w-4 mr-2" />
                Backend LLD
                {(backendDocFile || backendDocText.trim()) && (
                  <span className="ml-1 text-xs">✓</span>
                )}
              </Button>
              <Button
                onClick={() => setInputMode('frontend-lld')}
                disabled={isStreaming}
                variant={inputMode === 'frontend-lld' ? 'default' : 'ghost'}
                className={`flex items-center px-4 py-2 font-medium text-sm rounded-lg transition-all whitespace-nowrap ${
                  inputMode === 'frontend-lld'
                    ? 'shadow-md'
                    : 'hover:bg-muted'
                }`}
              >
                <BookOpen className="h-4 w-4 mr-2" />
                Frontend LLD
                {(frontendDocFile || frontendDocText.trim()) && (
                  <span className="ml-1 text-xs">✓</span>
                )}
              </Button>
            </div>

            {/* Tab Content */}
            <div className="mt-4">
              {inputMode === 'file' && (
                <FileUploadZone
                  onFileSelect={(file) => {
                    setSelectedFile(file);
                    setHasInteracted(true);
                  }}
                  disabled={isStreaming}
                />
              )}

              {inputMode === 'text' && (
                <div>
                  <Textarea
                    value={prdText}
                    onChange={(e) => {
                      setPrdText(e.target.value);
                      setHasInteracted(true);
                    }}
                    placeholder="Paste your PRD content here...

You can paste plain text, markdown, or any text-based PRD content.

Example:
# Feature: User Login
## Requirements
- Users must be able to login with email and password
- Password must be at least 8 characters
- Show error messages for invalid credentials"
                    className="h-64 font-mono resize-y"
                    disabled={isStreaming}
                    style={{ minHeight: '200px' }}
                  />
                  <div className="mt-2 flex items-center justify-between text-sm">
                    <p className="text-muted-foreground">
                      {prdText.length > 0 ? (
                        <span className="font-medium" style={{ color: "hsl(var(--primary))" }}>
                          {prdText.length} characters
                        </span>
                      ) : (
                        'Enter or paste your PRD text content'
                      )}
                    </p>
                    {prdText.length > 0 && !isStreaming && (
                      <Button
                        onClick={() => setPrdText('')}
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-800 font-medium"
                      >
                        Clear
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {inputMode === 'figma' && (
                <div>
                  <Input
                    type="url"
                    value={figmaUrl}
                    onChange={(e) => {
                      setFigmaUrl(e.target.value);
                      setHasInteracted(true);
                    }}
                    placeholder="https://www.figma.com/file/..."
                    disabled={isStreaming}
                  />
                  <p className="mt-2 text-sm text-muted-foreground flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-amber-500" />
                    <span>Paste your Figma design URL to generate test cases from your UI mockups</span>
                  </p>
                </div>
              )}

              {inputMode === 'screenshot' && (
                <div>
                  <div
                    className={`border-2 border-dashed border-input rounded-lg p-8 text-center transition-colors bg-muted ${
                      isStreaming ? 'opacity-50 cursor-not-allowed' : 'hover:border-primary cursor-pointer'
                    }`}
                    onClick={() => !isStreaming && document.getElementById('screenshot-input')?.click()}
                  >
                    <svg className="h-12 w-12 text-muted-foreground mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="text-foreground font-medium mb-1">
                      {screenshotFile ? screenshotFile.name : 'Upload Screenshot'}
                    </p>
                    <p className="text-sm text-muted-foreground mb-4">
                      Drop your screenshot here or click to browse
                    </p>
                    <span 
                      className="inline-block px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                      style={{
                        backgroundColor: "hsl(var(--primary) / 0.1)",
                        color: "hsl(var(--primary))"
                      }}
                    >
                      Select Screenshot
                    </span>
                    <input
                      id="screenshot-input"
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        if (e.target.files?.[0]) {
                          setScreenshotFile(e.target.files[0]);
                          setHasInteracted(true);
                        }
                      }}
                      disabled={isStreaming}
                      className="hidden"
                    />
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-amber-500" />
                    <span>Upload a screenshot of your flow or UI design to generate test cases using AI vision analysis</span>
                  </p>
                </div>
              )}

              {inputMode === 'backend-lld' && (
                <div>
                  <LLDDocumentInput
                    label="Backend LLD"
                    description="API specs, DB schema, request/response examples for comprehensive backend tests"
                    file={backendDocFile}
                    text={backendDocText}
                    onFileChange={setBackendDocFile}
                    onTextChange={setBackendDocText}
                    disabled={isStreaming}
                    type="backend"
                  />
                  <p className="mt-3 text-sm text-muted-foreground flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-amber-500" />
                    <span>Upload API specifications, database schema, or endpoint documentation for more accurate backend test cases</span>
                  </p>
                </div>
              )}

              {inputMode === 'frontend-lld' && (
                <div>
                  <LLDDocumentInput
                    label="Frontend LLD"
                    description="Screen flows, components, state management for comprehensive frontend tests"
                    file={frontendDocFile}
                    text={frontendDocText}
                    onFileChange={setFrontendDocFile}
                    onTextChange={setFrontendDocText}
                    disabled={isStreaming}
                    type="frontend"
                  />
                  <p className="mt-3 text-sm text-muted-foreground flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-amber-500" />
                    <span>Upload screen flows, component specs, or UI documentation for more accurate frontend test cases</span>
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Static Action Buttons - Always visible outside tab content */}
          <div className="mt-4 pt-4 border-t border-border">
            <div className="flex flex-col sm:flex-row gap-3">
              <Button
                onClick={handleStartAnalysis}
                disabled={!canAnalyze || isStreaming || savingToFeature}
                variant="default"
                size="lg"
                className="flex-1 font-semibold text-sm md:text-base rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-0.5 disabled:transform-none transition-all duration-200 min-h-[2.75rem]"
              >
                {savingToFeature ? (
                  <span className="flex items-center justify-center">
                    <Loader2
                      className="animate-spin -ml-1 mr-3 h-5 w-5"
                    />
                    Saving to Feature...
                  </span>
                ) : isStreaming ? (
                  <span className="flex items-center justify-center">
                    <Loader2
                      className="animate-spin -ml-1 mr-3 h-5 w-5"
                    />
                    Analyzing...
                  </span>
                ) : (
                  <>
                    {selectedFeature && 'Save & '}Start Analysis
                  </>
                )}
              </Button>

              {(isComplete || error) && (
                <Button
                  onClick={reset}
                  variant="secondary"
                  size="lg"
                  className="px-6 py-4 font-semibold shadow-lg"
                >
                  Reset
                </Button>
              )}
            </div>

            {/* Helper Text - Shows what will be analyzed or validation errors */}
            {!canAnalyze && hasInteracted ? (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-600 text-center flex items-center justify-center gap-2">
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  {!featureName.trim()
                    ? 'Enter a feature name to continue'
                    : 'Provide a PRD (file or text), screenshot, or Figma URL to continue'}
                </p>
              </div>
            ) : canAnalyze ? (
              <p className="mt-3 text-xs text-center font-medium flex items-center justify-center gap-2" style={{ color: "hsl(var(--primary))" }}>
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                {(() => {
                  // Build list of all selected inputs
                  const inputs = [];
                  
                  if (selectedFile) {
                    inputs.push(`PRD: ${selectedFile.name}`);
                  }
                  if (prdText.trim()) {
                    inputs.push('PRD Text');
                  }
                  if (figmaUrl.trim()) {
                    inputs.push('Figma Link');
                  }
                  if (screenshotFile) {
                    inputs.push(`Screenshot: ${screenshotFile.name}`);
                  }
                  
                  if (inputs.length === 0) {
                    return 'Ready to analyze';
                  }
                  
                  // Determine accuracy level
                  let accuracyNote = '';
                  if (inputs.length >= 2 && (selectedFile || prdText.trim()) && figmaUrl.trim()) {
                    accuracyNote = ' (Best Accuracy)';
                  } else if (inputs.length === 1) {
                    if (selectedFile || (prdText.trim() && !figmaUrl.trim())) {
                      accuracyNote = ' (Less Accuracy)';
                    } else {
                      accuracyNote = ' (Less Accuracy)';
                    }
                  }
                  
                  return `Will analyze: ${inputs.join(' + ')}${accuracyNote}`;
                })()}
              </p>
            ) : (
              <p className="mt-3 text-xs text-muted-foreground text-center">
                Enter a feature name and provide input to get started
              </p>
            )}
          </div>

          {/* Progress Section */}
          {isStreaming && (
            <div className="mt-6 animate-fade-in">
              <div className="flex items-center justify-between mb-3">
                <FormattedMessage
                  message={statusMessage}
                  className="text-base font-semibold text-primary animate-pulse"
                  textClassName="text-primary"
                />
                <span className="text-base font-bold text-primary">{progress}%</span>
              </div>
              <div 
                className="w-full bg-muted rounded-full h-4 shadow-inner"
                style={{ backgroundColor: "hsl(var(--muted))" }}
              >
                <div
                  className="bg-primary h-4 rounded-full transition-all duration-500 ease-out shadow-md"
                  style={{ 
                    width: `${progress}%`,
                    backgroundColor: "hsl(var(--primary))"
                  }}
                />
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-md">
              <p className="text-red-800 font-medium">Error: {error}</p>
            </div>
          )}
        </Card>

        {/* Backend Analysis Complete Summary */}
        {backendCompletionInfo && testScope === 'backend' && (
          <div
            className="rounded-2xl shadow-2xl p-6 md:p-8 mb-6 animate-fade-in border-2"
            style={{
              backgroundColor: "hsl(var(--card))",
              borderColor: "hsl(142 76% 36%)"
            }}
          >
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
              <div
                className="flex items-center justify-center w-12 h-12 rounded-xl shadow-lg"
                style={{ backgroundColor: "hsl(142 76% 36%)" }}
              >
                <Server className="h-7 w-7 text-white" />
              </div>
              <div>
                <h2 className="text-3xl font-bold text-foreground">Backend Analysis Complete!</h2>
                <p className="text-sm text-muted-foreground">API, Database, Security, and Performance test cases generated</p>
              </div>
            </div>

            {/* Feature Name */}
            <div
              className="backdrop-blur rounded-xl p-4 mb-6 border"
              style={{
                backgroundColor: "hsl(var(--muted))",
                borderColor: "hsl(var(--border))"
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <Target className="h-5 w-5 text-green-600" />
                <span className="text-sm font-semibold text-muted-foreground">Feature</span>
              </div>
              <h3 className="text-2xl font-bold text-foreground">{backendCompletionInfo.feature_name}</h3>
            </div>

            {/* Backend Metrics Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {/* API Tests */}
              <div className="backdrop-blur rounded-xl p-4 border transition-all hover:border-blue-500 bg-blue-50">
                <div className="flex items-center gap-2 mb-2">
                  <Server className="h-5 w-5 text-blue-600" />
                  <span className="text-xs font-semibold text-blue-700">API Tests</span>
                </div>
                <p className="text-3xl font-bold text-blue-800">{backendCompletionInfo.api_test_count}</p>
              </div>

              {/* Database Tests */}
              <div className="backdrop-blur rounded-xl p-4 border transition-all hover:border-purple-500 bg-purple-50">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="h-5 w-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                  </svg>
                  <span className="text-xs font-semibold text-purple-700">Database Tests</span>
                </div>
                <p className="text-3xl font-bold text-purple-800">{backendCompletionInfo.database_test_count}</p>
              </div>

              {/* Security Tests */}
              <div className="backdrop-blur rounded-xl p-4 border transition-all hover:border-red-500 bg-red-50">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="h-5 w-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                  <span className="text-xs font-semibold text-red-700">Security Tests</span>
                </div>
                <p className="text-3xl font-bold text-red-800">{backendCompletionInfo.security_test_count}</p>
              </div>

              {/* Performance Tests */}
              <div className="backdrop-blur rounded-xl p-4 border transition-all hover:border-green-500 bg-green-50">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="h-5 w-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span className="text-xs font-semibold text-green-700">Performance Tests</span>
                </div>
                <p className="text-3xl font-bold text-green-800">{backendCompletionInfo.performance_test_count}</p>
              </div>
            </div>

            {/* Download Button */}
            <div className="flex gap-3">
              <Button
                asChild
                variant="default"
                size="lg"
                className="flex-1 bg-green-600 hover:bg-green-700"
              >
                <a
                  href={`http://localhost:8000${backendCompletionInfo.backend_csv_path}`}
                  download
                >
                  <Download className="h-5 w-5" />
                  Download Backend Test Cases (CSV)
                </a>
              </Button>
            </div>
          </div>
        )}

        {/* Backend Test Cases Table */}
        {backendTestCases.length > 0 && testScope === 'backend' && (
          <div className="mb-6">
            <BackendTestCaseTable
              testCases={backendTestCases as BackendTestCase[]}
              csvPath={backendCompletionInfo?.backend_csv_path ? `http://localhost:8000${backendCompletionInfo.backend_csv_path}` : undefined}
            />
          </div>
        )}

        {/* Frontend Analysis Complete Summary */}
        {completionInfo && testScope === 'frontend' && (
          <div 
            className="rounded-2xl shadow-2xl p-6 md:p-8 mb-6 animate-fade-in border-2"
            style={{
              backgroundColor: "hsl(var(--card))",
              borderColor: "hsl(var(--border))"
            }}
          >
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
              <div 
                className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary shadow-lg"
                style={{ backgroundColor: "hsl(var(--primary))" }}
              >
                <CheckCircle2 className="h-7 w-7 text-primary-foreground" />
              </div>
              <div>
                <h2 className="text-3xl font-bold text-foreground">Analysis Complete!</h2>
                <p className="text-sm text-muted-foreground">Comprehensive test suite generated successfully</p>
              </div>
            </div>

            {/* Feature Name */}
            <div 
              className="backdrop-blur rounded-xl p-4 mb-6 border"
              style={{
                backgroundColor: "hsl(var(--muted))",
                borderColor: "hsl(var(--border))"
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <Target className="h-5 w-5 text-primary" />
                <span className="text-sm font-semibold text-muted-foreground">Feature</span>
              </div>
              <h3 className="text-2xl font-bold text-foreground">{completionInfo.feature_name}</h3>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {/* Test Points */}
              <div 
                className="backdrop-blur rounded-xl p-4 border transition-all hover:border-primary"
                style={{
                  backgroundColor: "hsl(var(--muted))",
                  borderColor: "hsl(var(--border))"
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <ClipboardList className="h-5 w-5" style={{ color: "hsl(var(--primary))" }} />
                  <span className="text-xs font-semibold text-muted-foreground">Test Points</span>
                </div>
                <p className="text-3xl font-bold" style={{ color: "hsl(var(--primary))" }}>{completionInfo.test_points_count}</p>
              </div>

              {/* Test Cases */}
              <div
                className="backdrop-blur rounded-xl p-4 border transition-all hover:border-primary"
                style={{
                  backgroundColor: "hsl(var(--muted))",
                  borderColor: "hsl(var(--border))"
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <FileCheck className="h-5 w-5" style={{ color: "hsl(var(--primary))" }} />
                  <span className="text-xs font-semibold text-muted-foreground">Test Cases</span>
                </div>
                <p className="text-3xl font-bold" style={{ color: "hsl(var(--primary))" }}>
                  {completionInfo.test_cases_count + (backendCompletionInfo?.test_cases_count || 0)}
                </p>
              </div>

              {/* Coverage Score */}
              <div 
                className="backdrop-blur rounded-xl p-4 border transition-all hover:border-primary"
                style={{
                  backgroundColor: "hsl(var(--muted))",
                  borderColor: "hsl(var(--border))"
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="h-5 w-5" style={{ color: "hsl(var(--primary))" }} />
                  <span className="text-xs font-semibold text-muted-foreground">Coverage</span>
                </div>
                <p className="text-3xl font-bold" style={{ color: "hsl(var(--primary))" }}>{completionInfo.coverage_score}%</p>
              </div>

              {/* Generated Time */}
              <div 
                className="backdrop-blur rounded-xl p-4 border transition-all hover:border-primary"
                style={{
                  backgroundColor: "hsl(var(--muted))",
                  borderColor: "hsl(var(--border))"
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Calendar className="h-5 w-5" style={{ color: "hsl(var(--primary))" }} />
                  <span className="text-xs font-semibold text-muted-foreground">Generated</span>
                </div>
                <p className="text-sm font-bold text-foreground">
                  {new Date(completionInfo.generated_at).toLocaleTimeString()}
                </p>
              </div>
            </div>

            {/* Download Buttons */}
            <div className="flex gap-3">
              <Button
                asChild
                variant="default"
                size="lg"
                className="flex-1"
              >
                <a
                  href={`http://localhost:8000${completionInfo.testcases_path}`}
                  download
                >
                  <Monitor className="h-5 w-5" />
                  Download Frontend CSV
                </a>
              </Button>
              {backendCompletionInfo?.backend_csv_path && (
                <Button
                  asChild
                  variant="default"
                  size="lg"
                  className="flex-1"
                >
                  <a
                    href={`http://localhost:8000${backendCompletionInfo.backend_csv_path}`}
                    download
                  >
                    <Database className="h-5 w-5" />
                    Download Backend CSV
                  </a>
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Coverage Insights - AI-powered analysis */}
        {completionInfo?.coverage_analysis && (
          <div className="mb-6">
            <CoverageInsights coverageAnalysis={completionInfo.coverage_analysis} />
          </div>
        )}

        {/* Test Visualization - Mindmap or Table View */}
        {(completionInfo || testCases.length > 0) && (
          <Card className="rounded-2xl shadow-xl p-8 mb-6">
            {/* Header with View Toggle */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-3xl font-bold text-foreground flex items-center gap-3">
                  <span 
                    className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-primary shadow-lg"
                    style={{ backgroundColor: "hsl(var(--primary))" }}
                  >
                    <Network className="h-6 w-6 text-primary-foreground" />
                  </span>
                  Test Coverage Visualization
                </h2>
                <p className="text-sm text-muted-foreground mt-1">Interactive view of your test hierarchy</p>
              </div>

              {/* View Mode Toggle */}
              <div className="flex gap-2 bg-muted p-1 rounded-lg">
                {/* Mindmap button - HIDDEN for now, will enhance later */}
                {false && (
                  <Button
                    onClick={() => setViewMode('mindmap')}
                    variant={viewMode === 'mindmap' ? 'default' : 'ghost'}
                    size="sm"
                    className={`flex items-center gap-2 ${
                      viewMode === 'mindmap'
                        ? 'bg-white text-primary shadow-md'
                        : ''
                    }`}
                  >
                    <Network className="h-4 w-4" />
                    Mindmap
                  </Button>
                )}
                <Button
                  onClick={() => setViewMode('table')}
                  variant={viewMode === 'table' ? 'default' : 'ghost'}
                  size="sm"
                  className={`flex items-center gap-2 ${
                    viewMode === 'table'
                      ? 'bg-white text-primary shadow-md'
                      : ''
                  }`}
                >
                  <Table className="h-4 w-4" />
                  Table
                </Button>
                <Button
                  onClick={() => setViewMode('detailed')}
                  variant={viewMode === 'detailed' ? 'default' : 'ghost'}
                  size="sm"
                  className={`flex items-center gap-2 ${
                    viewMode === 'detailed'
                      ? 'bg-white text-primary shadow-md'
                      : ''
                  }`}
                >
                  <FileCheck className="h-4 w-4" />
                  Detailed
                </Button>
                {truthTableEntries.length > 0 && (
                  <Button
                    onClick={() => setViewMode('truth_table')}
                    variant={viewMode === 'truth_table' ? 'default' : 'ghost'}
                    size="sm"
                    className={`flex items-center gap-2 ${
                      viewMode === 'truth_table'
                        ? 'bg-white text-primary shadow-md'
                        : ''
                    }`}
                  >
                    <ListChecks className="h-4 w-4" />
                    Truth Table ({truthTableEntries.length})
                  </Button>
                )}
              </div>
            </div>

            {/* Mindmap View - HIDDEN for now, will enhance later */}
            {viewMode === 'mindmap' && checklistMarkdown && (
              <div className="animate-fadeIn">
                <TestCaseMindmap markdown={checklistMarkdown} />
              </div>
            )}

            {/* Mindmap loading state */}
            {viewMode === 'mindmap' && !checklistMarkdown && completionInfo && (
              <div className="animate-fadeIn p-8 text-center">
                <div
                  className="inline-flex items-center justify-center w-16 h-16 rounded-full mb-4"
                  style={{ backgroundColor: "hsl(var(--foreground) / 0.1)" }}
                >
                  <Loader2 className="h-8 w-8 animate-spin" style={{ color: "hsl(var(--primary))" }} />
                </div>
                <p className="text-foreground">Loading mindmap visualization...</p>
              </div>
            )}

            {/* Mindmap not available yet (during streaming) */}
            {viewMode === 'mindmap' && !checklistMarkdown && !completionInfo && (
              <div className="animate-fadeIn p-8 text-center">
                <div
                  className="inline-flex items-center justify-center w-16 h-16 rounded-full mb-4"
                  style={{ backgroundColor: "hsl(var(--foreground) / 0.1)" }}
                >
                  <Loader2 className="h-8 w-8 animate-spin" style={{ color: "hsl(var(--primary))" }} />
                </div>
                <p className="text-foreground">Mindmap will be available after analysis completes</p>
                <p className="text-sm text-muted-foreground mt-2">Switch to Table View to see test cases as they stream in</p>
              </div>
            )}

            {/* Table View - COMPACT ELEGANT SHADCN UI DESIGN */}
            {viewMode === 'table' && (testCases.length > 0 || backendTestCases.length > 0) && (
              <div className="animate-fadeIn">
                {/* Filter Section - Top Most */}
                <div className="mb-6 space-y-4">
                  {/* Priority Filters */}
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-sm font-semibold text-foreground">Filter by Priority:</span>
                    {['P0', 'P1', 'P2'].map((priority) => (
                      <Button
                        key={priority}
                        onClick={() => {
                          const newSet = new Set(selectedPriorities);
                          if (newSet.has(priority)) {
                            newSet.delete(priority);
                          } else {
                            newSet.add(priority);
                          }
                          setSelectedPriorities(newSet);
                        }}
                        variant={selectedPriorities.has(priority) ? 'default' : 'outline'}
                        size="sm"
                        className={`flex items-center gap-2 ${
                          priority === 'P0'
                            ? selectedPriorities.has(priority)
                              ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                              : 'border-destructive text-destructive hover:bg-destructive/10'
                            : priority === 'P1'
                            ? selectedPriorities.has(priority)
                              ? 'bg-orange-500 text-white hover:bg-orange-600'
                              : 'border-orange-500 text-orange-600 hover:bg-orange-500/10'
                            : selectedPriorities.has(priority)
                              ? 'bg-primary text-primary-foreground'
                              : 'border-primary text-primary hover:bg-primary/10'
                        }`}
                      >
                        {priority === 'P0' && <AlertCircle className="h-3.5 w-3.5" />}
                        {priority === 'P1' && <AlertTriangle className="h-3.5 w-3.5" />}
                        {priority === 'P2' && <CheckCircle2 className="h-3.5 w-3.5" />}
                        <span>{priority}</span>
                      </Button>
                    ))}
                  </div>

                  {/* Test Type Filters (Backend/Frontend) */}
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-sm font-semibold text-foreground">Test Type:</span>
                    {testTypeOptions.map((option) => {
                      const Icon = option.icon;
                      const isSelected = selectedTestTypes.has(option.value);
                      // Count tests of each type
                      const count = option.value === 'backend' ? backendTestCases.length : testCases.length;
                      return (
                        <Button
                          key={option.value}
                          onClick={() => {
                            const newSet = new Set(selectedTestTypes);
                            if (newSet.has(option.value)) {
                              newSet.delete(option.value);
                            } else {
                              newSet.add(option.value);
                            }
                            setSelectedTestTypes(newSet);
                          }}
                          variant={isSelected ? 'default' : 'outline'}
                          size="sm"
                          className={`flex items-center gap-2 ${
                            isSelected
                              ? 'bg-primary text-primary-foreground'
                              : 'border-primary text-primary hover:bg-primary/10'
                          }`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          <span>{option.label} ({count})</span>
                        </Button>
                      );
                    })}
                  </div>
                </div>

                {/* Combined Test Cases - Frontend + Backend */}
                <div className="space-y-4">
                  {/* Frontend Test Cases */}
                  {(selectedTestTypes.size === 0 || selectedTestTypes.has('frontend')) && testCases
                    .filter((testCase) => selectedPriorities.has(testCase.priority))
                    .map((testCase, idx) => {
                  const priorityConfig = {
                    'P0': { 
                      cardBg: 'bg-destructive/5',
                      border: 'border-destructive/30',
                      badge: 'bg-destructive text-destructive-foreground',
                      icon: AlertCircle,
                      iconBg: 'bg-destructive/10',
                      iconColor: 'text-destructive'
                    },
                    'P1': { 
                      cardBg: 'bg-orange-500/5',
                      border: 'border-orange-500/30',
                      badge: 'bg-orange-500 text-white',
                      icon: AlertTriangle,
                      iconBg: 'bg-orange-500/10',
                      iconColor: 'text-orange-600'
                    },
                    'P2': { 
                      cardBg: 'bg-primary/5',
                      border: 'border-primary/30',
                      badge: 'bg-primary text-primary-foreground',
                      icon: CheckCircle2,
                      iconBg: 'bg-primary/10',
                      iconColor: 'text-primary'
                    },
                  };
                  const config = priorityConfig[testCase.priority as keyof typeof priorityConfig] || priorityConfig['P2'];
                  const PriorityIcon = config.icon;

                  return (
                    <Card
                      key={testCase.id}
                      className={`${config.cardBg} ${config.border} border-l-4 shadow-sm hover:shadow-md transition-all duration-300 animate-fade-in overflow-hidden relative`}
                      style={{ 
                        animationDelay: `${idx * 0.05}s`,
                        backgroundColor: testCase.priority === 'P0' 
                          ? "hsl(var(--destructive) / 0.05)"
                          : testCase.priority === 'P1'
                          ? "hsl(25 95% 53% / 0.05)"
                          : "hsl(var(--primary) / 0.05)",
                        borderLeftColor: testCase.priority === 'P0'
                          ? "hsl(var(--destructive) / 0.3)"
                          : testCase.priority === 'P1'
                          ? "hsl(25 95% 53% / 0.3)"
                          : "hsl(var(--primary) / 0.3)"
                      }}
                    >
                      {/* Top Right Corner - Frontend Badge and Notes Badge */}
                      <div className="absolute top-3 right-3 z-10 flex items-center gap-2">
                        {/* Frontend Badge */}
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/20">
                          <Monitor className="h-3.5 w-3.5 text-blue-600" />
                          <span className="text-xs font-semibold text-blue-700">Frontend</span>
                        </div>

                        {/* Notes Badge */}
                        {testCase.notes && (
                          <div
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 cursor-pointer hover:bg-amber-500/20 transition-colors"
                            title={testCase.notes}
                          >
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                            <span className="text-xs font-semibold text-amber-700">Critical</span>
                          </div>
                        )}
                      </div>

                      <CardHeader className="pb-3 pr-24">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-start gap-3 flex-1 min-w-0">
                            <div 
                              className={`flex items-center justify-center w-10 h-10 rounded-lg font-bold text-base flex-shrink-0 ${config.iconBg}`}
                              style={{ 
                                backgroundColor: testCase.priority === 'P0'
                                  ? "hsl(var(--destructive) / 0.1)"
                                  : testCase.priority === 'P1'
                                  ? "hsl(25 95% 53% / 0.1)"
                                  : "hsl(var(--primary) / 0.1)"
                              }}
                            >
                              <span className={config.iconColor}>{idx + 1}</span>
                        </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <CardTitle className="text-base mb-0">{testCase.feature}</CardTitle>
                                <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-bold ${config.badge}`}>
                                  <PriorityIcon className="h-3 w-3" />
                                  <span>{testCase.priority}</span>
                      </div>
                              </div>
                              <p className="text-xs font-mono text-muted-foreground truncate">{testCase.id}</p>
                            </div>
                          </div>
                        </div>
                      </CardHeader>

                      <CardContent className="space-y-4 pt-0">
                        {/* Requirement Section - Compact */}
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2">
                            <BookOpen className={`h-4 w-4 ${config.iconColor}`} />
                            <h5 className="text-xs font-semibold text-foreground uppercase tracking-wider">Requirement</h5>
                          </div>
                          <p className="text-sm text-foreground leading-relaxed pl-6">{testCase.requirement_description}</p>
                        </div>

                        {/* Test Steps Section - Compact */}
                        <div className="space-y-1.5 border-t border-border pt-3">
                          <div className="flex items-center gap-2">
                            <ListChecks className={`h-4 w-4 ${config.iconColor}`} />
                            <h5 className="text-xs font-semibold text-foreground uppercase tracking-wider">Test Steps</h5>
                          </div>
                          <div className="pl-6">
                            <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">{testCase.test_step}</p>
                          </div>
                        </div>

                        {/* Expected Result Section - Compact */}
                        <div className="space-y-1.5 border-t border-border pt-3">
                          <div className="flex items-center gap-2">
                                  <CheckCircle className="h-4 w-4" style={{ color: "hsl(var(--primary))" }} />
                            <h5 className="text-xs font-semibold text-foreground uppercase tracking-wider">Expected Result</h5>
                        </div>
                          <div className="pl-6">
                            {(() => {
                              // Parse expected_result into bullet points
                              // Split by | or newlines, and clean up
                              const results = testCase.expected_result
                                .split(/[|\n]/)
                                .map(r => r.trim())
                                .filter(r => r.length > 0)
                                .map(r => r.replace(/^✓\s*/, '').trim()) // Remove leading checkmarks
                                .filter(r => r.length > 0);
                              
                              return results.length > 0 ? (
                                <ul className="space-y-1.5 text-sm text-foreground leading-relaxed">
                                  {results.map((result, i) => (
                                    <li key={i} className="flex items-start gap-2">
                                      <CheckCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" style={{ color: "hsl(var(--primary))" }} />
                                      <span>{result}</span>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-sm text-foreground leading-relaxed">{testCase.expected_result}</p>
                              );
                            })()}
                          </div>
                      </div>

                      </CardContent>
                    </Card>
                  );
                })}

                  {/* Backend Test Cases */}
                  {(selectedTestTypes.size === 0 || selectedTestTypes.has('backend')) && backendTestCases
                    .filter((testCase) => selectedPriorities.has(testCase.priority))
                    .map((testCase, idx) => {
                      const priorityConfig = {
                        'P0': {
                          cardBg: 'bg-destructive/5',
                          border: 'border-destructive/30',
                          badge: 'bg-destructive text-destructive-foreground',
                          icon: AlertCircle,
                          iconBg: 'bg-destructive/10',
                          iconColor: 'text-destructive'
                        },
                        'P1': {
                          cardBg: 'bg-orange-500/5',
                          border: 'border-orange-500/30',
                          badge: 'bg-orange-500 text-white',
                          icon: AlertTriangle,
                          iconBg: 'bg-orange-500/10',
                          iconColor: 'text-orange-600'
                        },
                        'P2': {
                          cardBg: 'bg-primary/5',
                          border: 'border-primary/30',
                          badge: 'bg-primary text-primary-foreground',
                          icon: CheckCircle2,
                          iconBg: 'bg-primary/10',
                          iconColor: 'text-primary'
                        },
                      };
                      const config = priorityConfig[testCase.priority as keyof typeof priorityConfig] || priorityConfig['P2'];
                      const PriorityIcon = config.icon;

                      return (
                        <Card
                          key={testCase.test_case_id}
                          className={`${config.cardBg} ${config.border} border-l-4 shadow-sm hover:shadow-md transition-all duration-300 animate-fade-in overflow-hidden relative`}
                          style={{
                            animationDelay: `${idx * 0.05}s`,
                            backgroundColor: testCase.priority === 'P0'
                              ? "hsl(var(--destructive) / 0.05)"
                              : testCase.priority === 'P1'
                              ? "hsl(25 95% 53% / 0.05)"
                              : "hsl(var(--primary) / 0.05)",
                            borderLeftColor: testCase.priority === 'P0'
                              ? "hsl(var(--destructive) / 0.3)"
                              : testCase.priority === 'P1'
                              ? "hsl(25 95% 53% / 0.3)"
                              : "hsl(var(--primary) / 0.3)"
                          }}
                        >
                          {/* Backend Badge */}
                          <div className="absolute top-3 right-3 z-10 flex items-center gap-2">
                            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-green-500/10 border border-green-500/20">
                              <Database className="h-3.5 w-3.5 text-green-600" />
                              <span className="text-xs font-semibold text-green-700">Backend</span>
                            </div>
                          </div>

                          <CardHeader className="pb-3 pr-24">
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex items-start gap-3 flex-1 min-w-0">
                                <div
                                  className={`flex items-center justify-center w-10 h-10 rounded-lg font-bold text-base flex-shrink-0 ${config.iconBg}`}
                                  style={{
                                    backgroundColor: testCase.priority === 'P0'
                                      ? "hsl(var(--destructive) / 0.1)"
                                      : testCase.priority === 'P1'
                                      ? "hsl(25 95% 53% / 0.1)"
                                      : "hsl(var(--primary) / 0.1)"
                                  }}
                                >
                                  <span className={config.iconColor}>{testCases.length + idx + 1}</span>
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <CardTitle className="text-base mb-0">{testCase.category}</CardTitle>
                                    <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-bold ${config.badge}`}>
                                      <PriorityIcon className="h-3 w-3" />
                                      <span>{testCase.priority}</span>
                                    </div>
                                  </div>
                                  <p className="text-xs font-mono text-muted-foreground truncate">{testCase.test_case_id}</p>
                                </div>
                              </div>
                            </div>
                          </CardHeader>

                          <CardContent className="space-y-4 pt-0">
                            {/* API Component */}
                            <div className="space-y-1.5">
                              <div className="flex items-center gap-2">
                                <Server className={`h-4 w-4 ${config.iconColor}`} />
                                <h5 className="text-xs font-semibold text-foreground uppercase tracking-wider">API Component</h5>
                              </div>
                              <p className="text-sm text-foreground leading-relaxed pl-6">{testCase.api_component}</p>
                            </div>

                            {/* Test Scenario */}
                            <div className="space-y-1.5 border-t border-border pt-3">
                              <div className="flex items-center gap-2">
                                <ListChecks className={`h-4 w-4 ${config.iconColor}`} />
                                <h5 className="text-xs font-semibold text-foreground uppercase tracking-wider">Test Scenario</h5>
                              </div>
                              <div className="pl-6">
                                <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">{testCase.test_scenario}</p>
                              </div>
                            </div>

                            {/* Expected Result */}
                            <div className="space-y-1.5 border-t border-border pt-3">
                              <div className="flex items-center gap-2">
                                <CheckCircle className="h-4 w-4" style={{ color: "hsl(var(--primary))" }} />
                                <h5 className="text-xs font-semibold text-foreground uppercase tracking-wider">Expected Result</h5>
                              </div>
                              <div className="pl-6">
                                <p className="text-sm text-foreground leading-relaxed">{testCase.expected_result}</p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Test Points */}

        {/* Test Cases - Beautiful Modern Design (Only show if no completion info - for backward compat) */}
        {testCases.length > 0 && !completionInfo && (
          <Card className="rounded-2xl shadow-xl p-8 mb-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-3xl font-bold text-foreground flex items-center gap-3">
                  <span 
                    className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-primary shadow-lg"
                    style={{ backgroundColor: "hsl(var(--primary))" }}
                  >
                    <CheckCircle2 className="h-6 w-6 text-primary-foreground" />
                  </span>
                  Test Cases
                </h2>
                <p className="text-sm text-muted-foreground mt-1">{testCases.length} comprehensive test cases generated</p>
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {testCases.map((testCase, idx) => {
                // Priority color mapping
                const priorityColors = {
                  'P0': 'bg-red-100 text-red-800 border-red-200',
                  'P1': 'bg-orange-100 text-orange-800 border-orange-200',
                  'P2': 'bg-primary/10 text-primary border-primary/20',
                };
                const priorityColor = priorityColors[testCase.priority as keyof typeof priorityColors] || 'bg-gray-100 text-gray-800 border-gray-200';

                return (
                  <div
                    key={testCase.id}
                    className="group relative bg-card border-2 border-border rounded-xl p-6 hover:border-primary hover:shadow-2xl transition-all duration-300 animate-fade-in"
                    style={{ animationDelay: `${idx * 0.05}s` }}
                  >
                    {/* Header with ID and Priority */}
                    <div className="flex items-center justify-between mb-4 pb-4 border-b border-border">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 text-primary font-bold text-sm">
                          #{idx + 1}
                        </span>
                        <h3 className="font-bold text-lg text-foreground group-hover:text-primary transition-colors">
                          {testCase.feature}
                        </h3>
                      </div>
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border-2 ${priorityColor} shadow-sm`}>
                        {testCase.priority}
                      </span>
                    </div>

                    {/* Content Grid */}
                    <div className="space-y-4">
                      {/* Requirement */}
                      <div 
                        className="rounded-lg p-4 border"
                        style={{
                          backgroundColor: "hsl(var(--muted))",
                          borderColor: "hsl(var(--border))"
                        }}
                      >
                        <div className="flex items-start gap-2">
                          <span 
                            className="inline-flex items-center justify-center w-6 h-6 rounded-md flex-shrink-0 mt-0.5"
                            style={{
                              backgroundColor: "hsl(var(--primary))",
                              color: "hsl(var(--primary-foreground))"
                            }}
                          >
                            <BookOpen className="h-4 w-4" />
                          </span>
                          <div className="flex-1">
                            <p className="text-xs font-semibold text-foreground uppercase tracking-wide mb-1">Requirement</p>
                            <p className="text-sm text-foreground leading-relaxed">{testCase.requirement_description}</p>
                          </div>
                        </div>
                      </div>

                      {/* Test Steps */}
                      <div 
                        className="rounded-lg p-4 border"
                        style={{
                          backgroundColor: "hsl(var(--muted))",
                          borderColor: "hsl(var(--border))"
                        }}
                      >
                        <div className="flex items-start gap-2">
                          <span 
                            className="inline-flex items-center justify-center w-6 h-6 rounded-md flex-shrink-0 mt-0.5"
                            style={{
                              backgroundColor: "hsl(var(--primary))",
                              color: "hsl(var(--primary-foreground))"
                            }}
                          >
                            <PlayCircle className="h-4 w-4" />
                          </span>
                          <div className="flex-1">
                            <p className="text-xs font-semibold text-foreground uppercase tracking-wide mb-1">Test Steps</p>
                            <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">{testCase.test_step}</p>
                          </div>
                        </div>
                      </div>

                      {/* Expected Result */}
                      <div 
                        className="rounded-lg p-4 border"
                        style={{
                          backgroundColor: "hsl(var(--muted))",
                          borderColor: "hsl(var(--border))"
                        }}
                      >
                        <div className="flex items-start gap-2">
                          <span 
                            className="inline-flex items-center justify-center w-6 h-6 rounded-md flex-shrink-0 mt-0.5"
                            style={{
                              backgroundColor: "hsl(var(--primary))",
                              color: "hsl(var(--primary-foreground))"
                            }}
                          >
                            <CheckCircle className="h-4 w-4" />
                          </span>
                          <div className="flex-1">
                            <p className="text-xs font-semibold text-foreground uppercase tracking-wide mb-1">Expected Result</p>
                            <p className="text-sm text-foreground leading-relaxed">{testCase.expected_result}</p>
                          </div>
                        </div>
                      </div>

                      {/* Notes (if available) */}
                      {testCase.notes && (
                        <div 
                          className="rounded-lg p-4 border"
                          style={{
                            backgroundColor: "hsl(var(--muted))",
                            borderColor: "hsl(var(--border))"
                          }}
                        >
                          <div className="flex items-start gap-2">
                            <span 
                              className="inline-flex items-center justify-center w-6 h-6 rounded-md flex-shrink-0 mt-0.5"
                              style={{
                                backgroundColor: "hsl(var(--primary))",
                                color: "hsl(var(--primary-foreground))"
                              }}
                            >
                              <Info className="h-4 w-4" />
                            </span>
                            <div className="flex-1">
                              <p className="text-xs font-semibold text-foreground uppercase tracking-wide mb-1">Notes</p>
                              <p className="text-sm text-muted-foreground leading-relaxed">{testCase.notes}</p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Hover indicator */}
                    <div className="absolute top-0 right-0 w-1 h-full bg-gradient-to-b from-primary to-primary/80 rounded-r-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Detailed View - Professional Test Case Format */}
        {viewMode === 'detailed' && testCases.length > 0 && (
          <Card className="rounded-2xl shadow-xl border border-border p-6 bg-card">
            <TestCaseDetailView
              testCases={testCases.filter(tc => selectedPriorities.has(tc.priority))}
            />
          </Card>
        )}

        {/* Truth Table View - Navigation/Redirection Test Matrix */}
        {viewMode === 'truth_table' && truthTableEntries.length > 0 && (
          <TruthTableView entries={truthTableEntries} />
        )}

        {/* Completion Info */}
      </div>

      <style>{`
        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in {
          animation: fade-in 0.5s ease-out forwards;
        }
      `}</style>
    </div>
  );
}
