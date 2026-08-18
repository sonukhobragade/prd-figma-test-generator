import { useMemo, useState } from 'react';
import { Download, Search, AlertCircle, AlertTriangle, Clock, CheckCircle2, Route, Image as ImageIcon } from 'lucide-react';
import Papa from 'papaparse';
import type { CSVTestCase } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface TestCaseTableProps {
  testCases: CSVTestCase[];
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
  P3: {
    color: 'green',
    gradient: 'from-green-500 to-emerald-600',
    bg: 'bg-green-50',
    text: 'text-green-700',
    border: 'border-green-200',
    icon: CheckCircle2,
    label: 'Low',
  },
} as const;

const featureColors = [
  'from-blue-500 to-cyan-600',
  'from-purple-500 to-pink-600',
  'from-indigo-500 to-blue-600',
  'from-violet-500 to-purple-600',
  'from-fuchsia-500 to-pink-600',
  'from-cyan-500 to-teal-600',
];

export function TestCaseTable({ testCases }: TestCaseTableProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<string | null>(null);
  const [testTypeFilter, setTestTypeFilter] = useState<string | null>(null);

  const filteredTestCases = useMemo(() => {
    return testCases.filter((tc) => {
      const matchesSearch = searchQuery === '' ||
        tc.TestCaseID.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.Feature.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.RequirementDescription.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesPriority = priorityFilter === null || tc.Priority === priorityFilter;
      const matchesTestType = testTypeFilter === null || tc.TestType === testTypeFilter;

      return matchesSearch && matchesPriority && matchesTestType;
    });
  }, [testCases, searchQuery, priorityFilter, testTypeFilter]);

  const handleExportCSV = () => {
    // PapaParse automatically handles quoting for multiline content
    const csv = Papa.unparse(filteredTestCases);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    // Format: Frontend_FeatureName_Epoch.csv
    const epoch = Date.now();
    // Get feature name from first test case, sanitize it
    const featureName = testCases.length > 0
      ? testCases[0].Feature.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '')
      : 'Unknown';

    link.setAttribute('href', url);
    link.setAttribute('download', `Frontend_${featureName}_${epoch}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const priorityCounts = useMemo(() => {
    return testCases.reduce((acc, tc) => {
      acc[tc.Priority] = (acc[tc.Priority] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
  }, [testCases]);

  const getFeatureColor = (feature: string) => {
    const hash = feature.split('').reduce((acc, char) => char.charCodeAt(0) + acc, 0);
    return featureColors[hash % featureColors.length];
  };

  return (
    <Card className="p-8 animate-fadeIn">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-2xl font-bold">Test Cases</CardTitle>
            <CardDescription className="mt-1">{filteredTestCases.length} test cases generated</CardDescription>
          </div>
          <Button
            onClick={handleExportCSV}
            disabled={filteredTestCases.length === 0}
            variant="default"
            className="inline-flex items-center"
          >
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-8">

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search test cases..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Priority Filter */}
          <div className="flex gap-2 flex-wrap">
            <Button
              onClick={() => { setPriorityFilter(null); setTestTypeFilter(null); }}
              variant={priorityFilter === null && testTypeFilter === null ? 'default' : 'outline'}
              size="sm"
              className={priorityFilter === null && testTypeFilter === null ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg' : ''}
            >
              All ({testCases.length})
            </Button>
            {['P0', 'P1', 'P2', 'P3'].map((priority) => {
              const isActive = priorityFilter === priority;
              const colors = {
                P0: isActive ? 'bg-gradient-to-r from-red-500 to-pink-500 text-white shadow-lg' : 'bg-red-100 text-red-700 hover:bg-red-200 border-red-200',
                P1: isActive ? 'bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-lg' : 'bg-orange-100 text-orange-700 hover:bg-orange-200 border-orange-200',
                P2: isActive ? 'bg-gradient-to-r from-yellow-500 to-amber-500 text-white shadow-lg' : 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200 border-yellow-200',
                P3: isActive ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white shadow-lg' : 'bg-green-100 text-green-700 hover:bg-green-200 border-green-200',
              };
              return (
                <Button
                  key={priority}
                  onClick={() => setPriorityFilter(priority)}
                  variant={isActive ? 'default' : 'outline'}
                  size="sm"
                  className={colors[priority as keyof typeof colors]}
                >
                  {priority} ({priorityCounts[priority] || 0})
                </Button>
              );
            })}
          </div>

          {/* Test Type Filter */}
          <div className="flex gap-2 flex-wrap mt-3">
            <Button
              onClick={() => setTestTypeFilter('user_journey')}
              variant={testTypeFilter === 'user_journey' ? 'default' : 'outline'}
              size="sm"
              className={testTypeFilter === 'user_journey' ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg' : 'bg-purple-50 text-purple-700 hover:bg-purple-100 border-2 border-purple-200'}
            >
              <Route className="w-4 h-4" />
              User Journeys ({testCases.filter(tc => tc.TestType === 'user_journey').length})
            </Button>
            <Button
              onClick={() => setTestTypeFilter('positive')}
              variant={testTypeFilter === 'positive' ? 'default' : 'outline'}
              size="sm"
              className={testTypeFilter === 'positive' ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white shadow-lg' : 'bg-green-50 text-green-700 hover:bg-green-100'}
            >
              ✓ Positive ({testCases.filter(tc => tc.TestType === 'positive').length})
            </Button>
            <Button
              onClick={() => setTestTypeFilter('negative')}
              variant={testTypeFilter === 'negative' ? 'default' : 'outline'}
              size="sm"
              className={testTypeFilter === 'negative' ? 'bg-gradient-to-r from-red-500 to-rose-500 text-white shadow-lg' : 'bg-red-50 text-red-700 hover:bg-red-100'}
            >
              ✗ Negative ({testCases.filter(tc => tc.TestType === 'negative').length})
            </Button>
          </div>
        </div>
      </div>

      {filteredTestCases.length === 0 ? (
        <div className="text-center py-16 bg-gray-50 rounded-xl">
          <Search className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <p className="text-lg font-medium text-gray-700">No test cases found</p>
          <p className="text-sm text-gray-500 mt-1">Try adjusting your search or filters</p>
        </div>
      ) : (
        <div className="overflow-x-auto -mx-8 px-8 rounded-xl">
          <div className="inline-block min-w-full align-middle">
            <div className="overflow-hidden shadow-xl ring-1 ring-black ring-opacity-5 rounded-2xl">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                  <tr>
                    <th scope="col" className="px-6 py-5 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                      Screen
                    </th>
                    <th scope="col" className="px-6 py-5 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                      Test Case ID
                    </th>
                    <th scope="col" className="px-6 py-5 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                      Feature / Type
                    </th>
                    <th scope="col" className="px-6 py-5 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                      Requirement
                    </th>
                    <th scope="col" className="px-6 py-5 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                      Priority
                    </th>
                    <th scope="col" className="px-6 py-5 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                      Notes
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredTestCases.map((tc, index) => {
                    const PriorityIcon = priorityConfig[tc.Priority as keyof typeof priorityConfig]?.icon || Clock;
                    const config = priorityConfig[tc.Priority as keyof typeof priorityConfig];

                    return (
                      <tr
                        key={index}
                        className={`
                          transition-all duration-200 ease-in-out
                          hover:bg-gradient-to-r hover:from-purple-50/50 hover:via-indigo-50/30 hover:to-blue-50/50
                          hover:shadow-md hover:scale-[1.002]
                          ${index % 2 === 0 ? 'bg-white' : 'bg-gray-50/30'}
                          ${tc.TestType === 'user_journey' ? 'border-l-4 border-l-purple-500' : ''}
                        `}
                      >
                        {/* Screenshot Column */}
                        <td className="px-6 py-5">
                          {tc.ScreenshotURL ? (
                            <a
                              href={tc.ScreenshotURL}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="group block relative"
                            >
                              <img
                                src={tc.ScreenshotURL}
                                alt={`Screenshot for ${tc.Feature}`}
                                className="w-24 h-24 object-cover rounded-xl shadow-md
                                         group-hover:scale-110 group-hover:shadow-2xl
                                         transition-all duration-300 border-2 border-gray-200
                                         group-hover:border-purple-400"
                              />
                              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10
                                            rounded-xl transition-colors duration-300
                                            flex items-center justify-center">
                                <ImageIcon className="w-6 h-6 text-white opacity-0
                                                     group-hover:opacity-100 transition-opacity" />
                              </div>
                            </a>
                          ) : (
                            <div className="w-24 h-24 rounded-xl bg-gray-100
                                          flex items-center justify-center border-2 border-gray-200">
                              <ImageIcon className="w-8 h-8 text-gray-400" />
                            </div>
                          )}
                        </td>

                        {/* Test Case ID */}
                        <td className="px-6 py-5 whitespace-nowrap">
                          <div className="flex items-center">
                            <span className="font-mono text-sm font-semibold text-gray-900 tracking-tight">
                              {tc.TestCaseID}
                            </span>
                          </div>
                        </td>

                        {/* Feature & Test Type */}
                        <td className="px-6 py-5">
                          <div className="flex flex-col gap-2">
                            <span className={`
                              inline-flex items-center px-4 py-2 rounded-xl text-xs font-bold
                              bg-gradient-to-r ${getFeatureColor(tc.Feature)}
                              text-white shadow-lg transform hover:scale-105 transition-transform
                              w-fit
                            `}>
                              {tc.Feature}
                            </span>
                            {tc.TestType === 'user_journey' && (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full
                                             bg-gradient-to-r from-purple-500 to-pink-500
                                             text-white text-xs font-bold shadow-md w-fit">
                                <Route className="w-3 h-3" />
                                User Journey
                              </span>
                            )}
                          </div>
                        </td>

                        <td className="px-6 py-5 max-w-md">
                          <div className="text-sm text-gray-800 font-medium leading-relaxed line-clamp-2" title={tc.RequirementDescription}>
                            {tc.RequirementDescription}
                          </div>
                        </td>

                        <td className="px-6 py-5 whitespace-nowrap">
                          <div className={`
                            inline-flex items-center gap-2 px-4 py-2 rounded-xl
                            border-2 ${config?.border} ${config?.bg}
                            shadow-sm hover:shadow-md transition-all
                          `}>
                            <PriorityIcon className={`h-4 w-4 ${config?.text}`} />
                            <span className={`text-sm font-bold ${config?.text}`}>
                              {tc.Priority}
                            </span>
                          </div>
                        </td>

                        <td className="px-6 py-5 max-w-xs">
                          <div className="text-sm text-gray-600 leading-relaxed line-clamp-2" title={tc.Notes}>
                            {tc.Notes}
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
