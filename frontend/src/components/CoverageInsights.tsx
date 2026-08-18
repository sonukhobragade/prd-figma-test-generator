import { AlertCircle, CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface FeatureCoverage {
  feature: string;
  coverage_percentage: number;
  test_count: number;
  missing_scenarios: string[];
  risk_level: 'high' | 'medium' | 'low';
}

interface TestTypeDistribution {
  positive: number;
  negative: number;
  boundary: number;
  edge_case: number;
}

interface RiskAssessment {
  high_risk_features: string[];
  medium_risk_features: string[];
  low_risk_features: string[];
}

interface CoverageAnalysis {
  feature_coverage: FeatureCoverage[];
  test_type_distribution: TestTypeDistribution;
  missing_scenarios: string[];
  risk_assessment: RiskAssessment;
  recommendations: string[];
}

interface CoverageInsightsProps {
  coverageAnalysis: CoverageAnalysis | null | undefined;
}

export function CoverageInsights({ coverageAnalysis }: CoverageInsightsProps) {
  if (!coverageAnalysis) {
    return null;
  }

  const { feature_coverage, test_type_distribution, missing_scenarios, risk_assessment, recommendations } = coverageAnalysis;

  // Calculate total tests
  const totalTests =
    test_type_distribution.positive +
    test_type_distribution.negative +
    test_type_distribution.boundary +
    test_type_distribution.edge_case;

  // Calculate percentages
  const getPercentage = (count: number) => totalTests > 0 ? (count / totalTests * 100).toFixed(1) : '0';

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div 
          className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary shadow-lg"
          style={{ backgroundColor: "hsl(var(--primary))" }}
        >
          <TrendingUp className="h-6 w-6 text-primary-foreground" />
        </div>
        <div>
          <h3 className="text-2xl font-bold text-foreground">Coverage Insights</h3>
          <p className="text-sm text-muted-foreground">AI-powered test coverage analysis for QA teams</p>
        </div>
      </div>

      {/* Missing Scenarios Warning */}
      {missing_scenarios && missing_scenarios.length > 0 && (
        <Card className="border-2 border-amber-300 bg-gradient-to-br from-amber-50 to-orange-50">
          <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
              </div>
            </div>
            <div className="flex-1">
              <h4 className="text-lg font-bold text-amber-900 mb-2">Coverage Gaps Detected</h4>
              <ul className="space-y-1">
                {missing_scenarios.map((scenario, idx) => (
                  <li key={idx} className="text-sm text-amber-800 flex items-start">
                    <span className="mr-2">•</span>
                    <span>{scenario}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Test Type Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-bold">Test Type Distribution</CardTitle>
          </CardHeader>
          <CardContent>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-foreground">Positive Tests</span>
                <span className="text-sm font-bold text-green-600">{test_type_distribution.positive} ({getPercentage(test_type_distribution.positive)}%)</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-green-500 to-emerald-500 h-2 rounded-full transition-all"
                  style={{ width: `${getPercentage(test_type_distribution.positive)}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">Happy path scenarios</p>
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-foreground">Negative Tests</span>
                <span className="text-sm font-bold text-orange-600">{test_type_distribution.negative} ({getPercentage(test_type_distribution.negative)}%)</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-orange-500 to-red-500 h-2 rounded-full transition-all"
                  style={{ width: `${getPercentage(test_type_distribution.negative)}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">Error handling & invalid inputs</p>
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-foreground">Boundary Tests</span>
                <span className="text-sm font-bold text-blue-600">{test_type_distribution.boundary} ({getPercentage(test_type_distribution.boundary)}%)</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-blue-500 to-indigo-500 h-2 rounded-full transition-all"
                  style={{ width: `${getPercentage(test_type_distribution.boundary)}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">Min/max values & limits</p>
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium text-foreground">Edge Cases</span>
                <span className="text-sm font-bold text-purple-600">{test_type_distribution.edge_case} ({getPercentage(test_type_distribution.edge_case)}%)</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full transition-all"
                  style={{ width: `${getPercentage(test_type_distribution.edge_case)}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">Unusual scenarios & special conditions</p>
            </div>
          </div>

          {/* Distribution Warning */}
          {(test_type_distribution.negative / totalTests < 0.2 || test_type_distribution.edge_case / totalTests < 0.1) && (
            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-xs text-amber-800">
                <strong>Recommendation:</strong> {test_type_distribution.negative / totalTests < 0.2 && "Add more negative tests (target: 25-30%). "}{test_type_distribution.edge_case / totalTests < 0.1 && "Add more edge case tests (target: 15%)."}
              </p>
            </div>
          )}
          </CardContent>
        </Card>

        {/* Risk Assessment */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-bold">Risk Assessment</CardTitle>
          </CardHeader>
          <CardContent>
          <div className="space-y-4">
            {/* High Risk */}
            {risk_assessment.high_risk_features.length > 0 && (
              <div className="p-3 bg-red-50 border-l-4 border-red-600 rounded">
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="h-4 w-4 text-red-600" />
                  <span className="text-sm font-bold text-red-900">High Risk ({risk_assessment.high_risk_features.length})</span>
                </div>
                <ul className="space-y-1">
                  {risk_assessment.high_risk_features.map((feature, idx) => (
                    <li key={idx} className="text-xs text-red-800">• {feature}</li>
                  ))}
                </ul>
                <p className="text-xs text-red-700 mt-2 font-medium">Action: Add P0 tests immediately</p>
              </div>
            )}

            {/* Medium Risk */}
            {risk_assessment.medium_risk_features.length > 0 && (
              <div className="p-3 bg-amber-50 border-l-4 border-amber-600 rounded">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <span className="text-sm font-bold text-amber-900">Medium Risk ({risk_assessment.medium_risk_features.length})</span>
                </div>
                <ul className="space-y-1">
                  {risk_assessment.medium_risk_features.map((feature, idx) => (
                    <li key={idx} className="text-xs text-amber-800">• {feature}</li>
                  ))}
                </ul>
                <p className="text-xs text-amber-700 mt-2 font-medium">Action: Improve coverage to 70%+</p>
              </div>
            )}

            {/* Low Risk */}
            {risk_assessment.low_risk_features.length > 0 && (
              <div className="p-3 bg-green-50 border-l-4 border-green-600 rounded">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-bold text-green-900">Low Risk ({risk_assessment.low_risk_features.length})</span>
                </div>
                <ul className="space-y-1">
                  {risk_assessment.low_risk_features.map((feature, idx) => (
                    <li key={idx} className="text-xs text-green-800">• {feature}</li>
                  ))}
                </ul>
                <p className="text-xs text-green-700 mt-2 font-medium">Status: Well covered</p>
              </div>
            )}
          </div>
          </CardContent>
        </Card>
      </div>

      {/* Feature Coverage Breakdown */}
      {feature_coverage && feature_coverage.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-bold">Feature Coverage Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
          <div className="space-y-3">
            {feature_coverage.map((fc, idx) => (
              <div key={idx} className="border-l-4 border-border pl-4 py-2 hover:bg-muted/50 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-foreground">{fc.feature}</span>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      fc.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                      fc.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {fc.risk_level.toUpperCase()}
                    </span>
                    <span className="text-sm font-bold text-foreground">{fc.coverage_percentage.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground mb-2">
                  <span>{fc.test_count} test{fc.test_count !== 1 ? 's' : ''}</span>
                  {fc.missing_scenarios.length > 0 && (
                    <span className="text-amber-600">• {fc.missing_scenarios.length} gap{fc.missing_scenarios.length !== 1 ? 's' : ''}</span>
                  )}
                </div>
                {fc.missing_scenarios.length > 0 && (
                  <div className="mt-2 p-2 bg-amber-50 border border-amber-300 rounded text-xs">
                    <strong className="text-amber-800 font-semibold">Missing:</strong>
                    <ul className="mt-1 space-y-1">
                      {fc.missing_scenarios.map((ms, msIdx) => (
                        <li key={msIdx} className="text-gray-700">• {ms}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
          </CardContent>
        </Card>
      )}

      {/* AI Recommendations */}
      {recommendations && recommendations.length > 0 && (
        <Card className="border-l-4 border-primary bg-muted">
          <CardHeader>
            <CardTitle className="text-lg font-bold flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              AI Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent>
          <ul className="space-y-2">
            {recommendations.map((rec, idx) => (
              <li key={idx} className="text-sm text-foreground flex items-start">
                <span className="mr-2 text-primary font-bold">→</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
