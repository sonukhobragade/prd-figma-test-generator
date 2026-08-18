import { useMemo, useState } from 'react';
import { Download, Search, AlertCircle, AlertTriangle, Clock, CheckCircle2, XCircle, HelpCircle, ArrowRight, Navigation } from 'lucide-react';
import Papa from 'papaparse';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

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
}

interface TruthTableViewProps {
  entries: TruthTableEntry[];
}

const priorityConfig = {
  P0: {
    bg: 'bg-red-50',
    text: 'text-red-700',
    border: 'border-red-200',
    icon: AlertCircle,
    label: 'Critical',
  },
  P1: {
    bg: 'bg-orange-50',
    text: 'text-orange-700',
    border: 'border-orange-200',
    icon: AlertTriangle,
    label: 'High',
  },
  P2: {
    bg: 'bg-yellow-50',
    text: 'text-yellow-700',
    border: 'border-yellow-200',
    icon: Clock,
    label: 'Medium',
  },
} as const;

const resultConfig = {
  'Pass': {
    bg: 'bg-green-100',
    text: 'text-green-700',
    border: 'border-green-300',
    icon: CheckCircle2,
  },
  'Failed': {
    bg: 'bg-red-100',
    text: 'text-red-700',
    border: 'border-red-300',
    icon: XCircle,
  },
  'Not Tested': {
    bg: 'bg-gray-100',
    text: 'text-gray-700',
    border: 'border-gray-300',
    icon: HelpCircle,
  },
} as const;

const testTypeConfig = {
  'navigation': {
    label: 'Navigation',
    icon: Navigation,
    gradient: 'from-blue-500 to-cyan-600',
  },
  'payment_redirect': {
    label: 'Payment',
    icon: ArrowRight,
    gradient: 'from-green-500 to-emerald-600',
  },
  'state_transition': {
    label: 'State',
    icon: ArrowRight,
    gradient: 'from-purple-500 to-pink-600',
  },
  'deep_link': {
    label: 'Deep Link',
    icon: Navigation,
    gradient: 'from-indigo-500 to-blue-600',
  },
} as const;

export function TruthTableView({ entries }: TruthTableViewProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [featureFilter, setFeatureFilter] = useState<string | null>(null);
  const [testTypeFilter, setTestTypeFilter] = useState<string | null>(null);

  const features = useMemo(() => {
    return [...new Set(entries.map(e => e.feature))];
  }, [entries]);

  const filteredEntries = useMemo(() => {
    return entries.filter((entry) => {
      const matchesSearch = searchQuery === '' ||
        entry.screen.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entry.checkpoint.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entry.expected.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesFeature = featureFilter === null || entry.feature === featureFilter;
      const matchesTestType = testTypeFilter === null || entry.test_type === testTypeFilter;

      return matchesSearch && matchesFeature && matchesTestType;
    });
  }, [entries, searchQuery, featureFilter, testTypeFilter]);

  const handleExportCSV = () => {
    const csvData = filteredEntries.map(entry => ({
      'Screen': entry.screen,
      'CheckPoint': entry.checkpoint,
      'Failed (Redirected To)': entry.failed_redirect,
      'Pending (Redirected To)': entry.pending_redirect,
      'Successful (Redirected To)': entry.successful_redirect,
      'Auto Redirection (Failed)': entry.auto_redirect_failed,
      'Auto Redirection (Pending)': entry.auto_redirect_pending,
      'Auto Redirection (Successful)': entry.auto_redirect_success,
      'Results': entry.result,
      'Expected': entry.expected,
      'Feature': entry.feature,
      'Priority': entry.priority,
      'Test Type': entry.test_type,
    }));

    const csv = Papa.unparse(csvData);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    // Format: TruthTable_FeatureName_Epoch.csv
    const epoch = Date.now();
    const featureName = entries.length > 0
      ? entries[0].feature.replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '')
      : 'Unknown';
    link.setAttribute('download', `TruthTable_${featureName}_${epoch}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const testTypeCounts = useMemo(() => {
    return entries.reduce((acc, entry) => {
      acc[entry.test_type] = (acc[entry.test_type] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
  }, [entries]);

  if (entries.length === 0) {
    return null;
  }

  return (
    <Card className="p-8 animate-fadeIn">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-2xl font-bold flex items-center gap-2">
              <Navigation className="h-6 w-6 text-blue-600" />
              Truth Table / Test Matrix
            </CardTitle>
            <CardDescription className="mt-1">
              {filteredEntries.length} navigation/redirection test entries
            </CardDescription>
          </div>
          <Button
            onClick={handleExportCSV}
            disabled={filteredEntries.length === 0}
            variant="default"
            className="inline-flex items-center"
          >
            <Download className="h-4 w-4 mr-2" />
            Export Truth Table CSV
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
                placeholder="Search screens, checkpoints..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Feature Filter */}
            {features.length > 1 && (
              <div className="flex gap-2 flex-wrap">
                <Button
                  onClick={() => setFeatureFilter(null)}
                  variant={featureFilter === null ? 'default' : 'outline'}
                  size="sm"
                  className={featureFilter === null ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg' : ''}
                >
                  All Features ({entries.length})
                </Button>
                {features.map((feature) => (
                  <Button
                    key={feature}
                    onClick={() => setFeatureFilter(feature)}
                    variant={featureFilter === feature ? 'default' : 'outline'}
                    size="sm"
                    className={featureFilter === feature ? 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg' : ''}
                  >
                    {feature} ({entries.filter(e => e.feature === feature).length})
                  </Button>
                ))}
              </div>
            )}
          </div>

          {/* Test Type Filter */}
          <div className="flex gap-2 flex-wrap mt-3">
            <Button
              onClick={() => setTestTypeFilter(null)}
              variant={testTypeFilter === null ? 'default' : 'outline'}
              size="sm"
              className={testTypeFilter === null ? 'bg-gradient-to-r from-gray-600 to-gray-700 text-white' : ''}
            >
              All Types
            </Button>
            {Object.entries(testTypeConfig).map(([type, config]) => {
              const count = testTypeCounts[type] || 0;
              if (count === 0) return null;
              const TypeIcon = config.icon;
              return (
                <Button
                  key={type}
                  onClick={() => setTestTypeFilter(type)}
                  variant={testTypeFilter === type ? 'default' : 'outline'}
                  size="sm"
                  className={testTypeFilter === type ? `bg-gradient-to-r ${config.gradient} text-white shadow-lg` : ''}
                >
                  <TypeIcon className="w-4 h-4 mr-1" />
                  {config.label} ({count})
                </Button>
              );
            })}
          </div>
        </div>

        {filteredEntries.length === 0 ? (
          <div className="text-center py-16 bg-gray-50 rounded-xl">
            <Search className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <p className="text-lg font-medium text-gray-700">No truth table entries found</p>
            <p className="text-sm text-gray-500 mt-1">Try adjusting your search or filters</p>
          </div>
        ) : (
          <div className="overflow-x-auto -mx-8 px-8 rounded-xl">
            <div className="inline-block min-w-full align-middle">
              <div className="overflow-hidden shadow-xl ring-1 ring-black ring-opacity-5 rounded-2xl">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                    <tr>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Screen
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        CheckPoint
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Failed Redirect
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Pending Redirect
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Success Redirect
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Auto (F/P/S)
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Result
                      </th>
                      <th scope="col" className="px-4 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                        Priority
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredEntries.map((entry, index) => {
                      const priorityConf = priorityConfig[entry.priority];
                      const resultConf = resultConfig[entry.result];
                      const PriorityIcon = priorityConf?.icon || Clock;
                      const ResultIcon = resultConf?.icon || HelpCircle;
                      const testTypeConf = testTypeConfig[entry.test_type];

                      return (
                        <tr
                          key={entry.id || index}
                          className={`
                            transition-all duration-200 ease-in-out
                            hover:bg-gradient-to-r hover:from-blue-50/50 hover:via-indigo-50/30 hover:to-cyan-50/50
                            hover:shadow-md hover:scale-[1.002]
                            ${index % 2 === 0 ? 'bg-white' : 'bg-gray-50/30'}
                          `}
                        >
                          {/* Screen */}
                          <td className="px-4 py-4">
                            <div className="flex flex-col gap-1">
                              <span className="font-medium text-gray-900 text-sm">{entry.screen}</span>
                              <span className={`
                                inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium
                                bg-gradient-to-r ${testTypeConf.gradient} text-white w-fit
                              `}>
                                {testTypeConf.label}
                              </span>
                            </div>
                          </td>

                          {/* CheckPoint */}
                          <td className="px-4 py-4 max-w-xs">
                            <div className="text-sm text-gray-800 font-medium" title={entry.checkpoint}>
                              {entry.checkpoint}
                            </div>
                            <div className="text-xs text-gray-500 mt-1" title={entry.expected}>
                              {entry.expected.length > 60 ? entry.expected.substring(0, 60) + '...' : entry.expected}
                            </div>
                          </td>

                          {/* Failed Redirect */}
                          <td className="px-4 py-4">
                            <span className="text-sm text-red-600 bg-red-50 px-2 py-1 rounded">
                              {entry.failed_redirect}
                            </span>
                          </td>

                          {/* Pending Redirect */}
                          <td className="px-4 py-4">
                            <span className="text-sm text-yellow-600 bg-yellow-50 px-2 py-1 rounded">
                              {entry.pending_redirect}
                            </span>
                          </td>

                          {/* Success Redirect */}
                          <td className="px-4 py-4">
                            <span className="text-sm text-green-600 bg-green-50 px-2 py-1 rounded">
                              {entry.successful_redirect}
                            </span>
                          </td>

                          {/* Auto Redirects */}
                          <td className="px-4 py-4">
                            <div className="flex gap-1">
                              <span className={`text-xs px-1.5 py-0.5 rounded ${entry.auto_redirect_failed === 'Pass' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                                F:{entry.auto_redirect_failed}
                              </span>
                              <span className={`text-xs px-1.5 py-0.5 rounded ${entry.auto_redirect_pending === 'Pass' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                                P:{entry.auto_redirect_pending}
                              </span>
                              <span className={`text-xs px-1.5 py-0.5 rounded ${entry.auto_redirect_success === 'Pass' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                                S:{entry.auto_redirect_success}
                              </span>
                            </div>
                          </td>

                          {/* Result */}
                          <td className="px-4 py-4">
                            <div className={`
                              inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                              border ${resultConf?.border} ${resultConf?.bg}
                            `}>
                              <ResultIcon className={`h-4 w-4 ${resultConf?.text}`} />
                              <span className={`text-sm font-medium ${resultConf?.text}`}>
                                {entry.result}
                              </span>
                            </div>
                          </td>

                          {/* Priority */}
                          <td className="px-4 py-4">
                            <div className={`
                              inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                              border ${priorityConf?.border} ${priorityConf?.bg}
                            `}>
                              <PriorityIcon className={`h-4 w-4 ${priorityConf?.text}`} />
                              <span className={`text-sm font-bold ${priorityConf?.text}`}>
                                {entry.priority}
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
