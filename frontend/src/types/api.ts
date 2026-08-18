export interface TestCase {
  id: string;
  description: string;
  feature: string;
  priority: 'P0' | 'P1' | 'P2' | 'P3';
  test_type: string;
}

export interface AnalysisResponse {
  feature_name: string;
  test_points: TestCase[];
  coverage_score: number;
  generated_at: string;
  checklist_path: string;
  testcases_path: string;
  needs_more_info?: boolean;
  error_message?: string | null;
}

export interface CSVTestCase {
  TestCaseID: string;
  Feature: string;
  RequirementDescription: string;
  TestStep: string;
  ExpectedResult: string;
  Priority: string;
  Notes: string;
  ScreenshotURL?: string;
  TestType?: 'positive' | 'negative' | 'edge_case' | 'boundary' | 'user_journey';
}
