import { useState, useCallback, useRef } from 'react';

export interface TestPoint {
  id: string;
  description: string;
  feature: string;
  priority: string;
  test_type: string;
  index: number;
  total: number;
}

export interface TestCase {
  id: string;
  feature: string;
  requirement_description: string;
  test_step: string;
  expected_result: string;
  priority: string;
  notes: string;
  index: number;
  total: number;
  progress: number;
  test_type?: string;
  user_journey_tag?: string; // e.g., "new_user", "existing_user", "buy_subscription"
}

export interface TruthTableEntry {
  id: string;
  screen: string;
  checkpoint: string;
  failed_redirect: string;
  pending_redirect: string;
  successful_redirect: string;
  auto_redirect_failed: 'Pass' | 'NA';
  auto_redirect_pending: 'Pass' | 'NA';
  auto_redirect_success: 'Pass' | 'NA';
  result: 'Pass' | 'Failed' | 'Not Tested';
  expected: string;
  feature: string;
  priority: 'P0' | 'P1' | 'P2';
  test_type: 'navigation' | 'payment_redirect' | 'state_transition' | 'deep_link';
  index: number;
  total: number;
}

export interface StatusUpdate {
  type: string;
  message: string;
  progress: number;
}

export interface ChecklistGenerated {
  feature_name: string;
  test_points_count: number;
  truth_table_count: number;
  coverage_score: number;
  progress: number;
  coverage_analysis?: {
    feature_coverage: Array<{
      feature: string;
      coverage_percentage: number;
      test_count: number;
      missing_scenarios: string[];
      risk_level: 'high' | 'medium' | 'low';
    }>;
    test_type_distribution: {
      positive: number;
      negative: number;
      boundary: number;
      edge_case: number;
    };
    missing_scenarios: string[];
    risk_assessment: {
      high_risk_features: string[];
      medium_risk_features: string[];
      low_risk_features: string[];
    };
    recommendations: string[];
  };
}

export interface CoverageAnalysis {
  missing_scenarios: string[];
  recommendations: string[];
  risk_assessment: {
    high_risk_features: string[];
    medium_risk_features: string[];
    low_risk_features: string[];
  };
  test_type_distribution: {
    positive: number;
    negative: number;
    boundary: number;
    edge_case: number;
  };
  feature_coverage: Array<{
    feature: string;
    coverage_percentage: number;
    test_count: number;
    missing_scenarios: string[];
    risk_level: 'high' | 'medium' | 'low';
  }>;
}

export interface AnalysisComplete {
  feature_name: string;
  test_points_count: number;
  test_cases_count: number;
  truth_table_count: number;
  coverage_score: number;
  checklist_path: string;
  testcases_path: string;
  truth_table_path?: string;
  generated_at: string;
  progress: number;
  coverage_analysis?: CoverageAnalysis;
}

// Backend-specific types
export interface BackendTestPoint {
  id: string;
  category: string;
  subcategory: string;
  api_component: string;
  test_scenario: string;
  precondition: string;
  verification_method: string;
  expected_result: string;
  priority: 'P0' | 'P1' | 'P2';
  test_type: 'API' | 'Database' | 'Security' | 'Performance' | 'Config' | 'Analytics' | 'Backend' | 'Cache';
  index: number;
  total: number;
}

export interface BackendTestCase {
  test_case_id: string;
  category: string;
  subcategory: string;
  api_component: string;
  test_scenario: string;
  precondition: string;
  verification_method: string;
  expected_result: string;
  priority: 'P0' | 'P1' | 'P2';
  test_type: 'API' | 'Database' | 'Security' | 'Performance' | 'Config' | 'Analytics' | 'Backend' | 'Cache';
  index: number;
  total: number;
  progress: number;
}

export interface BackendChecklistGenerated {
  feature_name: string;
  test_points_count: number;
  api_test_count: number;
  database_test_count: number;
  security_test_count: number;
  performance_test_count: number;
  coverage_score: number;
  progress: number;
}

export interface BackendAnalysisComplete {
  feature_name: string;
  test_points_count: number;
  test_cases_count: number;
  api_test_count: number;
  database_test_count: number;
  security_test_count: number;
  performance_test_count: number;
  coverage_score: number;
  backend_csv_path: string;
  generated_at: string;
  progress: number;
  test_scope: 'backend';
}

export type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'complete' | 'error';

export interface StreamingState {
  status: StreamStatus;
  statusMessage: string;
  progress: number;
  testPoints: TestPoint[];
  testCases: TestCase[];
  truthTableEntries: TruthTableEntry[];
  checklistInfo: ChecklistGenerated | null;
  completionInfo: AnalysisComplete | null;
  error: string | null;
  // Backend-specific state
  testScope: 'frontend' | 'backend' | null;
  backendTestPoints: BackendTestPoint[];
  backendTestCases: BackendTestCase[];
  backendChecklistInfo: BackendChecklistGenerated | null;
  backendCompletionInfo: BackendAnalysisComplete | null;
  // Progress scaling for combined analysis
  progressOffset: number;
  progressScale: number;
}

export function useStreamingAnalysis() {
  const [state, setState] = useState<StreamingState>({
    status: 'idle',
    statusMessage: '',
    progress: 0,
    testPoints: [],
    testCases: [],
    truthTableEntries: [],
    checklistInfo: null,
    completionInfo: null,
    error: null,
    // Backend-specific initial state
    testScope: null,
    backendTestPoints: [],
    backendTestCases: [],
    backendChecklistInfo: null,
    backendCompletionInfo: null,
    // Progress scaling initial state
    progressOffset: 0,
    progressScale: 1.0,
  });

  // Helper to scale raw progress using offset and scale
  const scaleProgress = (rawProgress: number, offset: number, scale: number): number => {
    // Raw progress is 0-100, scale it to the appropriate range
    return Math.round(offset + (rawProgress * scale));
  };

  const eventSourceRef = useRef<EventSource | null>(null);

  const startAnalysis = useCallback((
    file: File | null,
    featureName?: string,
    applyMethods?: string,
    figmaUrl?: string,
    prdText?: string,
    llmProvider?: 'anthropic' | 'openai',
    llmApiKey?: string,
    frontendDocFile?: File | null,
    frontendDocText?: string,
    // VERSION TRACKING PARAMS
    version?: number,
    updateExisting?: boolean,
    // PROGRESS SCALING - for combined backend+frontend analysis
    progressOffset?: number, // Starting progress (default 0)
    progressScale?: number   // Scale factor (default 1.0 = 0-100%)
  ) => {
    const offset = progressOffset ?? 0;
    const scale = progressScale ?? 1.0;
    const hasFrontendLLD = frontendDocFile || (frontendDocText && frontendDocText.trim().length > 0);
    console.log('[ROCKET] Starting analysis...', { file, featureName, applyMethods, figmaUrl, prdText, llmProvider, hasFrontendLLD });

    // Determine if file is a screenshot or PRD (by MIME type)
    const isScreenshot = file && file.type.startsWith('image/');

    // Show immediate feedback - combined mode takes priority
    const initialMessage = hasFrontendLLD
      ? '[ROCKET] Starting comprehensive frontend test generation with LLD document...'
      : (figmaUrl && (file || prdText))
      ? '[ROCKET] Starting combined Figma + PRD analysis...'
      : isScreenshot && prdText
      ? '[ROCKET] Starting combined screenshot + text analysis...'
      : isScreenshot && figmaUrl
      ? '[ROCKET] Starting combined screenshot + Figma analysis...'
      : isScreenshot
      ? '[ROCKET] Starting screenshot analysis...'
      : figmaUrl
      ? '[ROCKET] Starting Figma design analysis...'
      : file || prdText
      ? '[ROCKET] Starting PRD analysis...'
      : '[ROCKET] Starting analysis...';

    // Reset state with immediate visual feedback
    // PRESERVE backend results if they exist (for combined backend+frontend analysis)
    const initialProgress = scaleProgress(5, offset, scale);
    setState(prev => ({
      status: 'connecting',
      statusMessage: initialMessage,
      progress: initialProgress,
      testPoints: [],
      testCases: [],
      truthTableEntries: [],
      checklistInfo: null,
      completionInfo: null,
      error: null,
      testScope: 'frontend',
      // Preserve backend results from previous analysis
      backendTestPoints: prev.backendTestPoints,
      backendTestCases: prev.backendTestCases,
      backendChecklistInfo: prev.backendChecklistInfo,
      backendCompletionInfo: prev.backendCompletionInfo,
      // Store progress scaling for handlers
      progressOffset: offset,
      progressScale: scale,
    }));

    // Determine endpoint and prepare FormData
    const formData = new FormData();
    let endpoint = 'http://localhost:8000/api/analyze-prd-stream';

    if (isScreenshot) {
      // Use screenshot streaming endpoint
      endpoint = 'http://localhost:8000/api/analyze-screenshot-stream';
      formData.append('screenshot', file); // Use 'screenshot' field name for backend compatibility

      // Add optional PRD text if provided
      if (prdText) {
        formData.append('prd_content', prdText);
      }
      if (figmaUrl) {
        // Note: backend may not support screenshot + Figma yet, but we prepare for it
        formData.append('figma_url', figmaUrl);
      }
    } else if (figmaUrl) {
      // Use Figma streaming endpoint (supports combined mode)
      endpoint = 'http://localhost:8000/api/analyze-figma-stream';
      formData.append('figma_url', figmaUrl);

      // Add PRD sources if provided (supports both file AND text simultaneously)
      if (file) {
        formData.append('prd_file', file);
      }
      if (prdText) {
        formData.append('prd_content', prdText);
      }
    } else if (file) {
      // Use PRD file streaming endpoint only
      formData.append('file', file);
    } else if (prdText) {
      // Convert PRD text to file for PRD-only mode
      const blob = new Blob([prdText], { type: 'text/plain' });
      const prdFile = new File([blob], 'prd_text.txt', { type: 'text/plain' });
      formData.append('file', prdFile);
    } else {
      setState(prev => ({
        ...prev,
        status: 'error',
        error: 'No file, text, screenshot, or Figma URL provided',
      }));
      return;
    }

    if (featureName) formData.append('feature_name', featureName);
    if (applyMethods) formData.append('apply_methods', applyMethods);
    if (llmProvider) formData.append('llm_provider', llmProvider);
    if (llmApiKey) formData.append('llm_api_key', llmApiKey);
    // VERSION TRACKING
    formData.append('version', String(version || 1));
    formData.append('update_existing', String(updateExisting || false));

    // Add Frontend LLD document (file takes priority over text)
    // Only add for PRD stream endpoint (not screenshot or figma endpoints)
    if (endpoint === 'http://localhost:8000/api/analyze-prd-stream') {
      if (frontendDocFile) {
        formData.append('frontend_doc_file', frontendDocFile);
      } else if (frontendDocText && frontendDocText.trim().length > 0) {
        formData.append('frontend_doc_content', frontendDocText.trim());
      }
    }

    // Upload file/URL and establish SSE connection
    fetch(endpoint, {
      method: 'POST',
      body: formData,
    })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('Response body is null');
        }

        setState(prev => ({ ...prev, status: 'streaming', statusMessage: 'Streaming data...' }));

        // Read the stream
        let currentEventType = '';

        // Create non-null reader reference for TypeScript
        const streamReader = reader;

        function processText({ done, value }: ReadableStreamReadResult<Uint8Array>): Promise<void> {
          if (done) {
            return Promise.resolve();
          }

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('event:')) {
              currentEventType = line.substring(6).trim();
              continue;
            }

            if (line.startsWith('data:')) {
              const dataStr = line.substring(5).trim();
              if (!dataStr) continue;

              try {
                const data = JSON.parse(dataStr);
                console.log('📥 SSE Event:', currentEventType, data);

                // Handle different event types based on the event: line
                if (currentEventType === 'status') {
                  console.log('🔄 Handling status update:', data);
                  handleStatusUpdate(data);
                } else if (currentEventType === 'checklist_generated') {
                  console.log('📋 Handling checklist:', data);
                  handleChecklistGenerated(data);
                } else if (currentEventType === 'test_point') {
                  console.log('🎯 Handling test point:', data);
                  handleTestPoint(data);
                } else if (currentEventType === 'test_case') {
                  console.log('✅ Handling test case:', data);
                  handleTestCase(data);
                } else if (currentEventType === 'truth_table_entry') {
                  console.log('📊 Handling truth table entry:', data);
                  handleTruthTableEntry(data);
                } else if (currentEventType === 'complete') {
                  console.log('🎉 Handling complete:', data);
                  handleComplete(data);
                } else if (currentEventType === 'error') {
                  console.log('❌ Handling error:', data);
                  handleError(data.message || 'Unknown error');
                } else {
                  console.warn('⚠️ Unknown event type:', currentEventType, data);
                }

                // Reset event type after processing
                currentEventType = '';
              } catch (e) {
                console.error('Error parsing SSE data:', e, dataStr);
              }
            }
          }

          return streamReader.read().then(processText);
        }

        return streamReader.read().then(processText);
      })
      .catch(error => {
        console.error('Streaming error:', error);
        setState(prev => ({
          ...prev,
          status: 'error',
          error: error.message,
          statusMessage: `Error: ${error.message}`,
        }));
      });
  }, []);

  const handleStatusUpdate = (data: StatusUpdate) => {
    setState(prev => ({
      ...prev,
      statusMessage: data.message,
      progress: scaleProgress(data.progress, prev.progressOffset, prev.progressScale),
    }));
  };

  const handleChecklistGenerated = (data: ChecklistGenerated) => {
    setState(prev => ({
      ...prev,
      checklistInfo: data,
      progress: scaleProgress(data.progress, prev.progressOffset, prev.progressScale),
      statusMessage: `Generated checklist with ${data.test_points_count} test points`,
    }));
  };

  const handleTestPoint = (data: TestPoint) => {
    setState(prev => ({
      ...prev,
      testPoints: [...prev.testPoints, data],
      statusMessage: `Received test point ${data.index + 1}/${data.total}`,
    }));
  };

  const handleTestCase = (data: TestCase) => {
    setState(prev => ({
      ...prev,
      testCases: [...prev.testCases, data],
      progress: scaleProgress(data.progress, prev.progressOffset, prev.progressScale),
      statusMessage: `Generated test case ${data.index + 1}/${data.total}`,
    }));
  };

  const handleTruthTableEntry = (data: TruthTableEntry) => {
    setState(prev => ({
      ...prev,
      truthTableEntries: [...prev.truthTableEntries, data],
      statusMessage: `Received truth table entry ${data.index + 1}/${data.total}`,
    }));
  };

  const handleComplete = (data: AnalysisComplete) => {
    setState(prev => ({
      ...prev,
      status: 'complete',
      completionInfo: data,
      progress: scaleProgress(100, prev.progressOffset, prev.progressScale),
      statusMessage: `Complete! Generated ${data.test_cases_count} test cases`,
    }));
  };

  const handleError = (message: string) => {
    setState(prev => ({
      ...prev,
      status: 'error',
      error: message,
      statusMessage: `Error: ${message}`,
    }));
  };

  const reset = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setState({
      status: 'idle',
      statusMessage: '',
      progress: 0,
      testPoints: [],
      testCases: [],
      truthTableEntries: [],
      checklistInfo: null,
      completionInfo: null,
      error: null,
      testScope: null,
      backendTestPoints: [],
      backendTestCases: [],
      backendChecklistInfo: null,
      backendCompletionInfo: null,
      progressOffset: 0,
      progressScale: 1.0,
    });
  }, []);

  // Backend-specific event handlers
  const handleBackendTestPoint = (data: BackendTestPoint) => {
    setState(prev => ({
      ...prev,
      backendTestPoints: [...prev.backendTestPoints, data],
      statusMessage: `Received backend test point ${data.index + 1}/${data.total}`,
    }));
  };

  const handleBackendTestCase = (data: BackendTestCase) => {
    setState(prev => ({
      ...prev,
      backendTestCases: [...prev.backendTestCases, data],
      progress: scaleProgress(data.progress, prev.progressOffset, prev.progressScale),
      statusMessage: `Generated backend test case ${data.index + 1}/${data.total}`,
    }));
  };

  const handleBackendChecklistGenerated = (data: BackendChecklistGenerated) => {
    setState(prev => ({
      ...prev,
      backendChecklistInfo: data,
      progress: scaleProgress(data.progress, prev.progressOffset, prev.progressScale),
      statusMessage: `Generated backend checklist with ${data.test_points_count} test points`,
    }));
  };

  const handleBackendComplete = (data: BackendAnalysisComplete) => {
    setState(prev => ({
      ...prev,
      status: 'complete',
      backendCompletionInfo: data,
      progress: scaleProgress(100, prev.progressOffset, prev.progressScale),
      statusMessage: `Complete! Generated ${data.test_cases_count} backend test cases`,
    }));
  };

  // Start backend analysis
  const startBackendAnalysis = useCallback((
    file: File | null,
    featureName?: string,
    llmProvider?: 'anthropic' | 'openai',
    llmApiKey?: string,
    prdText?: string,
    backendDocFile?: File | null,
    backendDocText?: string,
    // VERSION TRACKING PARAMS
    version?: number,
    updateExisting?: boolean,
    // PROGRESS SCALING - for combined backend+frontend analysis
    progressOffset?: number, // Starting progress (default 0)
    progressScale?: number   // Scale factor (default 1.0 = 0-100%)
  ) => {
    const offset = progressOffset ?? 0;
    const scale = progressScale ?? 1.0;
    const hasBackendLLD = backendDocFile || (backendDocText && backendDocText.trim().length > 0);
    console.log('[SERVER] Starting BACKEND analysis...', { file, featureName, llmProvider, hasBackendLLD, offset, scale });

    const initialMessage = hasBackendLLD
      ? '[SERVER] Starting comprehensive backend test generation with LLD document...'
      : '[SERVER] Starting backend test case generation (API, Database, Security)...';

    // Reset state with immediate visual feedback
    const initialProgress = scaleProgress(5, offset, scale);
    setState({
      status: 'connecting',
      statusMessage: initialMessage,
      progress: initialProgress,
      testPoints: [],
      testCases: [],
      truthTableEntries: [],
      checklistInfo: null,
      completionInfo: null,
      error: null,
      testScope: 'backend',
      backendTestPoints: [],
      backendTestCases: [],
      backendChecklistInfo: null,
      backendCompletionInfo: null,
      // Store progress scaling for handlers
      progressOffset: offset,
      progressScale: scale,
    });

    // Prepare FormData
    const formData = new FormData();
    const endpoint = 'http://localhost:8000/api/analyze-prd-backend-stream';

    if (file) {
      formData.append('file', file);
    } else if (prdText) {
      // Convert PRD text to file
      const blob = new Blob([prdText], { type: 'text/plain' });
      const prdFile = new File([blob], 'prd_text.txt', { type: 'text/plain' });
      formData.append('file', prdFile);
    } else {
      setState(prev => ({
        ...prev,
        status: 'error',
        error: 'No file or text provided for backend analysis',
      }));
      return;
    }

    if (featureName) formData.append('feature_name', featureName);
    if (llmProvider) formData.append('llm_provider', llmProvider);
    if (llmApiKey) formData.append('llm_api_key', llmApiKey);
    // VERSION TRACKING
    formData.append('version', String(version || 1));
    formData.append('update_existing', String(updateExisting || false));

    // Add Backend LLD document (file takes priority over text)
    if (backendDocFile) {
      formData.append('backend_doc_file', backendDocFile);
    } else if (backendDocText && backendDocText.trim().length > 0) {
      formData.append('backend_doc_content', backendDocText.trim());
    }

    // Upload file and establish SSE connection
    fetch(endpoint, {
      method: 'POST',
      body: formData,
    })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('Response body is null');
        }

        setState(prev => ({ ...prev, status: 'streaming', statusMessage: 'Streaming backend test data...' }));

        let currentEventType = '';
        const streamReader = reader;

        function processText({ done, value }: ReadableStreamReadResult<Uint8Array>): Promise<void> {
          if (done) {
            return Promise.resolve();
          }

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('event:')) {
              currentEventType = line.substring(6).trim();
              continue;
            }

            if (line.startsWith('data:')) {
              const dataStr = line.substring(5).trim();
              if (!dataStr) continue;

              try {
                const data = JSON.parse(dataStr);
                console.log('[SERVER] SSE Event:', currentEventType, data);

                // Handle backend-specific event types
                if (currentEventType === 'status') {
                  handleStatusUpdate(data);
                } else if (currentEventType === 'backend_checklist_generated') {
                  handleBackendChecklistGenerated(data);
                } else if (currentEventType === 'backend_test_point') {
                  handleBackendTestPoint(data);
                } else if (currentEventType === 'backend_test_case') {
                  handleBackendTestCase(data);
                } else if (currentEventType === 'complete') {
                  handleBackendComplete(data);
                } else if (currentEventType === 'error') {
                  handleError(data.message || 'Unknown error');
                } else {
                  console.warn('[SERVER] Unknown event type:', currentEventType, data);
                }

                currentEventType = '';
              } catch (e) {
                console.error('Error parsing SSE data:', e, dataStr);
              }
            }
          }

          return streamReader.read().then(processText);
        }

        return streamReader.read().then(processText);
      })
      .catch(error => {
        console.error('Backend streaming error:', error);
        setState(prev => ({
          ...prev,
          status: 'error',
          error: error.message,
          statusMessage: `Error: ${error.message}`,
        }));
      });
  }, []);

  return {
    ...state,
    startAnalysis,
    startBackendAnalysis,
    reset,
    isStreaming: state.status === 'streaming' || state.status === 'connecting',
    isComplete: state.status === 'complete',
    hasError: state.status === 'error',
  };
}
