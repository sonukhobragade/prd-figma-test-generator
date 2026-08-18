import { useMemo, useState } from 'react';
import { Download, Search, AlertCircle, AlertTriangle, Clock, Server, Database, Shield, Gauge, Settings, BarChart } from 'lucide-react';
import Papa from 'papaparse';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

// Backend test case interface matching the CSV format
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
}

interface BackendTestCaseTableProps {
  testCases: BackendTestCase[];
  csvPath?: string;
}

const priorityConfig = {
  P0: {
    color: 'red',
    gradient: 'from-red-500 to-rose-600',
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
    icon: AlertCircle,
    label: 'Critical',
  },
  P1: {
    color: 'orange',
    gradient: 'from-orange-500 to-amber-600',
    bg: 'bg-orange-50',
    text: 'text-orange-700',
    border: 'border-orange-200',
    icon: AlertTriangle,
    label: 'High',
  },
  P2: {
    color: 'yellow',
    gradient: 'from-yellow-500 to-amber-500',
    bg: 'bg-yellow-50',
    text: 'text-yellow-700',
    border: 'border-yellow-200',
    icon: Clock,
    label: 'Medium',
  },
} as const;

const testTypeConfig = {
  API: {
    icon: Server,
    color: 'from-blue-500 to-cyan-600',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    border: 'border-blue-200',
  },
  Database: {
    icon: Database,
    color: 'from-purple-500 to-indigo-600',
    bg: 'bg-purple-50',
    text: 'text-purple-700',
    border: 'border-purple-200',
  },
  Security: {
    icon: Shield,
    color: 'from-red-500 to-pink-600',
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
  },
  Performance: {
    icon: Gauge,
    color: 'from-green-500 to-emerald-600',
    bg: 'bg-green-50',
    text: 'text-green-700',
    border: 'border-green-200',
  },
  Config: {
    icon: Settings,
    color: 'from-gray-500 to-slate-600',
    bg: 'bg-gray-50',
    text: 'text-gray-700',
    border: 'border-gray-200',
  },
  Analytics: {
    icon: BarChart,
    color: 'from-amber-500 to-orange-600',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
  },
  Backend: {
    icon: Server,
    color: 'from-indigo-500 to-violet-600',
    bg: 'bg-indigo-50',
    text: 'text-indigo-700',
    border: 'border-indigo-200',
  },
  Cache: {
    icon: Database,
    color: 'from-cyan-500 to-teal-600',
    bg: 'bg-cyan-50',
    text: 'text-cyan-700',
    border: 'border-cyan-200',
  },
} as const;

const categoryColors = [
  'from-blue-500 to-cyan-600',
  'from-purple-500 to-pink-600',
  'from-indigo-500 to-blue-600',
  'from-violet-500 to-purple-600',
  'from-fuchsia-500 to-pink-600',
  'from-cyan-500 to-teal-600',
];

export function BackendTestCaseTable({ testCases, csvPath }: BackendTestCaseTableProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null);
  const [testTypeFilter, setTestTypeFilter] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const filteredTestCases = useMemo(() => {
    return testCases.filter((tc) => {
      const matchesSearch = searchQuery === '' ||
        tc.test_case_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.api_component.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.test_scenario.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesPriority = priorityFilter === null || tc.priority === priorityFilter;
      const matchesTestType = testTypeFilter === null || tc.test_type === testTypeFilter;
      const matchesCategory = categoryFilter === null || tc.category === categoryFilter;

      return matchesSearch && matchesPriority && matchesTestType && matchesCategory;
    });
  }, [testCases, searchQuery, priorityFilter, testTypeFilter, categoryFilter]);

  const handleExportCSV = () => {
    // If we have a CSV path from the backend, download directly
    if (csvPath) {
      window.open(csvPath, '_blank');
      return;
    }

    // Otherwise generate CSV client-side - preserve newlines for multiline content
    const csvData = filteredTestCases.map(tc => ({
      'Test Case ID': tc.test_case_id ?? '',
      'Category': tc.category ?? '',
      'Subcategory': tc.subcategory ?? '',
      'API/Component': tc.api_component ?? '',
      'Test Scenario': tc.test_scenario ?? '',
      'Precondition': tc.precondition ?? '',
      'Verification Method': tc.verification_method ?? '',
      'Expected Result': tc.expected_result ?? '',
      'Priority': tc.priority ?? '',
      'Test Type': tc.test_type ?? '',
      'DEV Status': '',
      'QA Status': '',
      'Comments': '',
    }));

    const csv = Papa.unparse(csvData);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    // Format: Backend_FeatureName_Epoch.csv
    const epoch = Date.now();
    // Get feature name from first test case category, sanitize it
    const featureName = testCases.length > 0
      ? testCases[0].category.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '')
      : 'Unknown';

    link.setAttribute('href', url);
    link.setAttribute('download', `Backend_${featureName}_${epoch}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const priorityCounts = useMemo(() => {
    return testCases.reduce((acc, tc) => {
      acc[tc.priority] = (acc[tc.priority] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
  }, [testCases]);

  const testTypeCounts = useMemo(() => {
    return testCases.reduce((acc, tc) => {
      acc[tc.test_type] = (acc[tc.test_type] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
  }, [testCases]);

  const categories = useMemo(() => {
    return [...new Set(testCases.map(tc => tc.category))];
  }, [testCases]);

  const getCategoryColor = (category: string) => {
    const hash = category.split('').reduce((acc, char) => char.charCodeAt(0) + acc, 0);
    return categoryColors[hash % categoryColors.length];
  };

  return (
    <Card className="p-8 animate-fadeIn">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-2xl font-bold flex items-center gap-2">
              <Server className="h-6 w-6 text-green-600" />
              Backend Test Cases
            </CardTitle>
            <CardDescription className="mt-1">
              {filteredTestCases.length} backend test cases generated (API, Database, Security, Performance)
            </CardDescription>
          </div>
          <Button
            onClick={handleExportCSV}
            disabled={filteredTestCases.length === 0}
            variant="default"
            className="inline-flex items-center bg-green-600 hover:bg-green-700"
          >
            <Download className="h-4 w-4 mr-2" />
            Export Backend CSV
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {/* Summary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="p-4 rounded-xl bg-blue-50 border border-blue-200">
            <div className="flex items-center gap-2">
              <Server className="h-5 w-5 text-blue-600" />
              <span className="text-sm font-medium text-blue-700">API Tests</span>
            </div>
            <p className="text-2xl font-bold text-blue-800 mt-1">{testTypeCounts['API'] || 0}</p>
          </div>
          <div className="p-4 rounded-xl bg-purple-50 border border-purple-200">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-purple-600" />
              <span className="text-sm font-medium text-purple-700">Database Tests</span>
            </div>
            <p className="text-2xl font-bold text-purple-800 mt-1">{testTypeCounts['Database'] || 0}</p>
          </div>
          <div className="p-4 rounded-xl bg-red-50 border border-red-200">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-red-600" />
              <span className="text-sm font-medium text-red-700">Security Tests</span>
            </div>
            <p className="text-2xl font-bold text-red-800 mt-1">{testTypeCounts['Security'] || 0}</p>
          </div>
          <div className="p-4 rounded-xl bg-green-50 border border-green-200">
            <div className="flex items-center gap-2">
              <Gauge className="h-5 w-5 text-green-600" />
              <span className="text-sm font-medium text-green-700">Performance Tests</span>
            </div>
            <p className="text-2xl font-bold text-green-800 mt-1">{testTypeCounts['Performance'] || 0}</p>
          </div>
        </div>

        <div className="mb-8">
          {/* Filters */}
          <div className="flex flex-col gap-4">
            {/* Search */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search backend test cases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Priority Filter */}
            <div className="flex gap-2 flex-wrap">
              <Button
                onClick={() => { setPriorityFilter(null); setTestTypeFilter(null); setCategoryFilter(null); }}
                variant={priorityFilter === null && testTypeFilter === null && categoryFilter === null ? 'default' : 'outline'}
                size="sm"
                className={priorityFilter === null && testTypeFilter === null && categoryFilter === null ? 'bg-gradient-to-r from-green-600 to-emerald-600 text-white shadow-lg' : ''}
              >
                All ({testCases.length})
              </Button>
              {['P0', 'P1', 'P2'].map((priority) => {
                const isActive = priorityFilter === priority;
                const config = priorityConfig[priority as keyof typeof priorityConfig];
                return (
                  <Button
                    key={priority}
                    onClick={() => setPriorityFilter(priority)}
                    variant={isActive ? 'default' : 'outline'}
                    size="sm"
                    className={isActive ? `bg-gradient-to-r ${config.gradient} text-white shadow-lg` : `${config.bg} ${config.text} hover:bg-opacity-80 ${config.border}`}
                  >
                    {priority} ({priorityCounts[priority] || 0})
                  </Button>
                );
              })}
            </div>

            {/* Test Type Filter */}
            <div className="flex gap-2 flex-wrap">
              {Object.entries(testTypeConfig).map(([type, config]) => {
                const count = testTypeCounts[type] || 0;
                if (count === 0) return null;
                const isActive = testTypeFilter === type;
                const IconComponent = config.icon;
                return (
                  <Button
                    key={type}
                    onClick={() => setTestTypeFilter(type)}
                    variant={isActive ? 'default' : 'outline'}
                    size="sm"
                    className={isActive ? `bg-gradient-to-r ${config.color} text-white shadow-lg` : `${config.bg} ${config.text} hover:bg-opacity-80 ${config.border}`}
                  >
                    <IconComponent className="w-4 h-4 mr-1" />
                    {type} ({count})
                  </Button>
                );
              })}
            </div>

            {/* Category Filter */}
            {categories.length > 1 && (
              <div className="flex gap-2 flex-wrap">
                <span className="text-sm text-muted-foreground self-center mr-2">Categories:</span>
                {categories.slice(0, 6).map((category) => {
                  const isActive = categoryFilter === category;
                  return (
                    <Button
                      key={category}
                      onClick={() => setCategoryFilter(isActive ? null : category)}
                      variant={isActive ? 'default' : 'outline'}
                      size="sm"
                      className={isActive ? `bg-gradient-to-r ${getCategoryColor(category)} text-white shadow-lg` : 'bg-gray-50 text-gray-700 hover:bg-gray-100'}
                    >
                      {category}
                    </Button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {filteredTestCases.length === 0 ? (
          <div className="text-center py-16 bg-gray-50 rounded-xl">
            <Search className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <p className="text-lg font-medium text-gray-700">No backend test cases found</p>
            <p className="text-sm text-gray-500 mt-1">Try adjusting your search or filters</p>
          </div>
        ) : (
          <div className="overflow-x-auto -mx-8 px-8 rounded-xl">
            <div className="inline-block min-w-full align-middle">
              <div className="overflow-hidden shadow-xl ring-1 ring-black ring-opacity-5 rounded-2xl">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gradient-to-r from-green-50 to-emerald-50">
                    <tr>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Test Case ID
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Category
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        API/Component
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Test Scenario
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Verification
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Type
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Priority
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredTestCases.map((tc, index) => {
                      const PriorityIcon = priorityConfig[tc.priority]?.icon || Clock;
                      const priorityConf = priorityConfig[tc.priority];
                      const typeConf = testTypeConfig[tc.test_type];
                      const TypeIcon = typeConf?.icon || Server;

                      return (
                        <tr
                          key={index}
                          className={`
                            transition-all duration-200 ease-in-out
                            hover:bg-gradient-to-r hover:from-green-50/50 hover:via-emerald-50/30 hover:to-teal-50/50
                            hover:shadow-md hover:scale-[1.002]
                            ${index % 2 === 0 ? 'bg-white' : 'bg-gray-50/30'}
                          `}
                        >
                          {/* Test Case ID */}
                          <td className="px-4 py-4 whitespace-nowrap">
                            <span className="font-mono text-sm font-semibold text-gray-900 tracking-tight">
                              {tc.test_case_id}
                            </span>
                          </td>

                          {/* Category & Subcategory */}
                          <td className="px-4 py-4">
                            <div className="flex flex-col gap-1">
                              <span className={`
                                inline-flex items-center px-3 py-1 rounded-lg text-xs font-bold
                                bg-gradient-to-r ${getCategoryColor(tc.category)}
                                text-white shadow-sm w-fit
                              `}>
                                {tc.category}
                              </span>
                              <span className="text-xs text-gray-500 truncate max-w-32" title={tc.subcategory}>
                                {tc.subcategory}
                              </span>
                            </div>
                          </td>

                          {/* API/Component */}
                          <td className="px-4 py-4 max-w-40">
                            <code className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-800 font-mono block truncate" title={tc.api_component}>
                              {tc.api_component}
                            </code>
                          </td>

                          {/* Test Scenario */}
                          <td className="px-4 py-4 max-w-xs">
                            <div className="text-sm text-gray-800 font-medium leading-relaxed line-clamp-2" title={tc.test_scenario}>
                              {tc.test_scenario}
                            </div>
                          </td>

                          {/* Verification Method */}
                          <td className="px-4 py-4 max-w-32">
                            <span className="text-xs text-gray-600 line-clamp-2" title={tc.verification_method}>
                              {tc.verification_method}
                            </span>
                          </td>

                          {/* Test Type */}
                          <td className="px-4 py-4 whitespace-nowrap">
                            <div className={`
                              inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                              ${typeConf?.bg} ${typeConf?.border} border
                            `}>
                              <TypeIcon className={`h-3.5 w-3.5 ${typeConf?.text}`} />
                              <span className={`text-xs font-semibold ${typeConf?.text}`}>
                                {tc.test_type}
                              </span>
                            </div>
                          </td>

                          {/* Priority */}
                          <td className="px-4 py-4 whitespace-nowrap">
                            <div className={`
                              inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                              border ${priorityConf?.border} ${priorityConf?.bg}
                            `}>
                              <PriorityIcon className={`h-3.5 w-3.5 ${priorityConf?.text}`} />
                              <span className={`text-xs font-bold ${priorityConf?.text}`}>
                                {tc.priority}
                              </span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
