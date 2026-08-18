import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Circle,
  Tag,
  AlertTriangle,
  Clock,
  CheckCheck,
  XCircle,
  MessageSquare,
  FileText,
  ListChecks,
  Target,
  User,
  Smartphone,
  Copy,
} from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface TestCase {
  id: string;
  feature: string;
  requirement_description: string;
  test_step: string;
  expected_result: string;
  priority: string;
  test_type?: string;
  notes?: string;
  preconditions?: string;
  user_type?: string;
  category?: string;
  screen_reference?: string;
  dev_status?: 'Not Started' | 'In Progress' | 'Done' | 'Blocked';
  qa_status?: 'Not Started' | 'Passed' | 'Failed' | 'Not Ready' | 'Blocked';
  comments?: string;
  dev_comments?: string;
}

interface TestCaseDetailViewProps {
  testCases: TestCase[];
  // Future: onStatusChange?: (id: string, field: string, value: string) => void;
}

const priorityConfig: Record<string, { color: string; bg: string; border: string }> = {
  P0: { color: 'text-red-700', bg: 'bg-red-100', border: 'border-red-400' },
  P1: { color: 'text-orange-700', bg: 'bg-orange-100', border: 'border-orange-400' },
  P2: { color: 'text-yellow-700', bg: 'bg-yellow-100', border: 'border-yellow-400' },
  P3: { color: 'text-green-700', bg: 'bg-green-100', border: 'border-green-400' },
};

const statusConfig = {
  'Not Started': { icon: Circle, color: 'text-gray-500', bg: 'bg-gray-100' },
  'In Progress': { icon: Clock, color: 'text-blue-600', bg: 'bg-blue-100' },
  'Done': { icon: CheckCheck, color: 'text-green-600', bg: 'bg-green-100' },
  'Passed': { icon: CheckCircle2, color: 'text-green-600', bg: 'bg-green-100' },
  'Failed': { icon: XCircle, color: 'text-red-600', bg: 'bg-red-100' },
  'Not Ready': { icon: Clock, color: 'text-yellow-600', bg: 'bg-yellow-100' },
  'Blocked': { icon: AlertTriangle, color: 'text-orange-600', bg: 'bg-orange-100' },
};

function TestCaseCard({ testCase, index }: { testCase: TestCase; index: number }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedSections, setExpandedSections] = useState({
    requirement: true,
    steps: true,
    expected: true,
  });

  const priority = priorityConfig[testCase.priority] || priorityConfig.P2;
  const devStatus = statusConfig[testCase.dev_status || 'Not Started'];
  const qaStatus = statusConfig[testCase.qa_status || 'Not Started'];
  const DevIcon = devStatus.icon;
  const QaIcon = qaStatus.icon;

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Parse test steps into array
  const parseSteps = (steps: string): string[] => {
    if (!steps) return [];
    // Split by numbered patterns like "1.", "2." or newlines
    const lines = steps.split(/(?:\d+\.\s*|\n|;)/).filter(s => s.trim());
    return lines.length > 0 ? lines : [steps];
  };

  // Parse expected results into array
  const parseExpectedResults = (results: string): string[] => {
    if (!results) return [];
    const lines = results.split(/(?:\n|;|•)/).filter(s => s.trim());
    return lines.length > 0 ? lines : [results];
  };

  const steps = parseSteps(testCase.test_step);
  const expectedResults = parseExpectedResults(testCase.expected_result);

  const copyToClipboard = () => {
    const text = `
Test Case: ${testCase.id}
Feature: ${testCase.feature}
Priority: ${testCase.priority}

REQUIREMENT:
${testCase.requirement_description}

TEST STEPS:
${steps.map((s, i) => `${i + 1}. ${s}`).join('\n')}

EXPECTED RESULT:
${expectedResults.map(r => `• ${r}`).join('\n')}
    `.trim();
    navigator.clipboard.writeText(text);
  };

  return (
    <Card className={`mb-4 border-l-4 ${priority.border} shadow-sm hover:shadow-md transition-all`}>
      {/* Header */}
      <CardHeader
        className="pb-2 cursor-pointer select-none"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-start justify-between gap-4">
          {/* Left: ID, Title, Tags */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              {/* Index Number */}
              <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-muted text-sm font-bold text-muted-foreground">
                {index + 1}
              </span>

              {/* Title */}
              <h3 className="text-base font-semibold text-foreground truncate">
                {testCase.feature}
              </h3>

              {/* Priority Badge */}
              <span className={`px-2 py-0.5 rounded text-xs font-bold ${priority.bg} ${priority.color}`}>
                {testCase.priority}
              </span>

              {/* Test Type Tag */}
              {testCase.test_type && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-primary/10 text-xs font-medium text-primary">
                  <Tag className="h-3 w-3" />
                  {testCase.test_type}
                </span>
              )}
            </div>

            {/* Test Case ID */}
            <p className="text-xs text-muted-foreground font-mono ml-11">
              {testCase.id}
            </p>
          </div>

          {/* Right: Status & Actions */}
          <div className="flex items-center gap-2">
            {/* Dev Status */}
            <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${devStatus.bg}`}>
              <DevIcon className={`h-3 w-3 ${devStatus.color}`} />
              <span className={`font-medium ${devStatus.color}`}>Dev</span>
            </div>

            {/* QA Status */}
            <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${qaStatus.bg}`}>
              <QaIcon className={`h-3 w-3 ${qaStatus.color}`} />
              <span className={`font-medium ${qaStatus.color}`}>QA</span>
            </div>

            {/* Expand Icon */}
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      {/* Expanded Content */}
      {isExpanded && (
        <CardContent className="pt-0 space-y-4">
          {/* Quick Info Bar */}
          {(testCase.user_type || testCase.screen_reference || testCase.category) && (
            <div className="flex flex-wrap gap-3 px-3 py-2 bg-muted/50 rounded-lg text-xs">
              {testCase.category && (
                <span className="flex items-center gap-1 text-muted-foreground">
                  <FileText className="h-3 w-3" />
                  {testCase.category}
                </span>
              )}
              {testCase.user_type && (
                <span className="flex items-center gap-1 text-muted-foreground">
                  <User className="h-3 w-3" />
                  {testCase.user_type}
                </span>
              )}
              {testCase.screen_reference && (
                <span className="flex items-center gap-1 text-muted-foreground">
                  <Smartphone className="h-3 w-3" />
                  {testCase.screen_reference}
                </span>
              )}
            </div>
          )}

          {/* REQUIREMENT Section */}
          <div className="border rounded-lg overflow-hidden">
            <button
              onClick={() => toggleSection('requirement')}
              className="w-full flex items-center justify-between px-4 py-2 bg-amber-50 hover:bg-amber-100 transition-colors"
            >
              <span className="flex items-center gap-2 text-sm font-semibold text-amber-800">
                <FileText className="h-4 w-4" />
                REQUIREMENT
              </span>
              {expandedSections.requirement ? (
                <ChevronDown className="h-4 w-4 text-amber-600" />
              ) : (
                <ChevronRight className="h-4 w-4 text-amber-600" />
              )}
            </button>
            {expandedSections.requirement && (
              <div className="px-4 py-3 bg-white">
                <p className="text-sm text-foreground leading-relaxed">
                  {testCase.requirement_description}
                </p>
                {testCase.preconditions && (
                  <div className="mt-2 pt-2 border-t border-dashed">
                    <span className="text-xs font-medium text-muted-foreground">Preconditions: </span>
                    <span className="text-xs text-foreground">{testCase.preconditions}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* TEST STEPS Section */}
          <div className="border rounded-lg overflow-hidden">
            <button
              onClick={() => toggleSection('steps')}
              className="w-full flex items-center justify-between px-4 py-2 bg-blue-50 hover:bg-blue-100 transition-colors"
            >
              <span className="flex items-center gap-2 text-sm font-semibold text-blue-800">
                <ListChecks className="h-4 w-4" />
                TEST STEPS
              </span>
              {expandedSections.steps ? (
                <ChevronDown className="h-4 w-4 text-blue-600" />
              ) : (
                <ChevronRight className="h-4 w-4 text-blue-600" />
              )}
            </button>
            {expandedSections.steps && (
              <div className="px-4 py-3 bg-white">
                <ol className="space-y-2">
                  {steps.map((step, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex-shrink-0 mt-0.5">
                        {i + 1}
                      </span>
                      <span className="text-sm text-foreground leading-relaxed">{step.trim()}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>

          {/* EXPECTED RESULT Section */}
          <div className="border rounded-lg overflow-hidden">
            <button
              onClick={() => toggleSection('expected')}
              className="w-full flex items-center justify-between px-4 py-2 bg-green-50 hover:bg-green-100 transition-colors"
            >
              <span className="flex items-center gap-2 text-sm font-semibold text-green-800">
                <Target className="h-4 w-4" />
                EXPECTED RESULT
              </span>
              {expandedSections.expected ? (
                <ChevronDown className="h-4 w-4 text-green-600" />
              ) : (
                <ChevronRight className="h-4 w-4 text-green-600" />
              )}
            </button>
            {expandedSections.expected && (
              <div className="px-4 py-3 bg-white">
                <ul className="space-y-2">
                  {expectedResults.map((result, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <Circle className="h-4 w-4 text-green-500 flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-foreground leading-relaxed">{result.trim()}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Comments Section */}
          {(testCase.comments || testCase.dev_comments || testCase.notes) && (
            <div className="border rounded-lg p-4 bg-muted/30">
              <div className="flex items-center gap-2 mb-2">
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium text-muted-foreground">Comments</span>
              </div>
              {testCase.comments && (
                <p className="text-sm text-foreground mb-2">
                  <span className="font-medium text-muted-foreground">QA: </span>
                  {testCase.comments}
                </p>
              )}
              {testCase.dev_comments && (
                <p className="text-sm text-foreground mb-2">
                  <span className="font-medium text-muted-foreground">Dev: </span>
                  {testCase.dev_comments}
                </p>
              )}
              {testCase.notes && !testCase.comments && !testCase.dev_comments && (
                <p className="text-sm text-foreground">{testCase.notes}</p>
              )}
            </div>
          )}

          {/* Action Bar */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t">
            <Button variant="ghost" size="sm" onClick={copyToClipboard}>
              <Copy className="h-4 w-4 mr-1" />
              Copy
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

export function TestCaseDetailView({ testCases }: TestCaseDetailViewProps) {
  const [expandAll, setExpandAll] = useState(false);

  // Group test cases by feature/category
  const groupedTestCases = testCases.reduce((acc, tc) => {
    const key = tc.feature || 'Uncategorized';
    if (!acc[key]) acc[key] = [];
    acc[key].push(tc);
    return acc;
  }, {} as Record<string, TestCase[]>);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Test Cases</h2>
          <p className="text-sm text-muted-foreground">{testCases.length} test cases</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setExpandAll(!expandAll)}
        >
          {expandAll ? 'Collapse All' : 'Expand All'}
        </Button>
      </div>

      {/* Test Case List */}
      <div className="space-y-6">
        {Object.entries(groupedTestCases).map(([feature, cases]) => (
          <div key={feature}>
            {/* Feature Header */}
            <div className="flex items-center gap-2 mb-3 pb-2 border-b">
              <div className="w-1 h-6 rounded-full bg-primary" />
              <h3 className="text-base font-semibold text-foreground">{feature}</h3>
              <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                {cases.length} tests
              </span>
            </div>

            {/* Test Cases */}
            {cases.map((tc, index) => (
              <TestCaseCard key={tc.id} testCase={tc} index={index} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
