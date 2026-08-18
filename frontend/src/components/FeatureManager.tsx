import { useState, useEffect } from 'react';
import {
  FolderKanban,
  Plus,
  FileText,
  Palette,
  Code2,
  Trash2,
  ChevronRight,
  RefreshCw,
  Loader2,
  Tag,
  X,
  Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface Feature {
  id: string;
  name: string;
  keywords: string[];
  description: string;
  created_at: string;
  updated_at: string;
  prd_count: number;
  figma_count: number;
  test_count: number;
  codebase_files: number;
}

interface FeatureDocument {
  id: string;
  feature_id: string;
  doc_type: 'prd' | 'figma' | 'codebase';
  name: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

interface FeatureManagerProps {
  onSelectFeature?: (feature: Feature | null) => void;
  selectedFeatureId?: string | null;
  compact?: boolean;
}

export function FeatureManager({
  onSelectFeature,
  selectedFeatureId,
  compact = false,
}: FeatureManagerProps) {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [expandedFeature, setExpandedFeature] = useState<string | null>(null);
  const [featureDocuments, setFeatureDocuments] = useState<{
    prds: FeatureDocument[];
    figmas: FeatureDocument[];
  } | null>(null);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Create form state
  const [newName, setNewName] = useState('');
  const [newKeywords, setNewKeywords] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchFeatures = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/features');
      const data = await response.json();

      if (data.success) {
        setFeatures(data.features);
        setError(null);
      } else {
        setError(data.message || 'Failed to load features');
      }
    } catch (err) {
      setError('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeatures();
  }, []);

  const handleCreateFeature = async () => {
    if (!newName.trim() || !newKeywords.trim()) return;

    setCreating(true);
    try {
      const formData = new FormData();
      formData.append('name', newName);
      formData.append('keywords', newKeywords);
      formData.append('description', newDescription);

      const response = await fetch('/api/features', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.success) {
        setFeatures([...features, data.feature]);
        setShowCreateForm(false);
        setNewName('');
        setNewKeywords('');
        setNewDescription('');

        // Select the new feature
        if (onSelectFeature) {
          onSelectFeature(data.feature);
        }
      } else {
        setError(data.detail || 'Failed to create feature');
      }
    } catch (err) {
      setError('Failed to create feature');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteFeature = async (featureId: string) => {
    if (!confirm('Delete this feature and all linked documents?')) return;

    try {
      const response = await fetch(`/api/features/${featureId}`, {
        method: 'DELETE',
      });

      const data = await response.json();

      if (data.success) {
        setFeatures(features.filter((f) => f.id !== featureId));
        if (selectedFeatureId === featureId && onSelectFeature) {
          onSelectFeature(null);
        }
      }
    } catch (err) {
      setError('Failed to delete feature');
    }
  };

  const handleExpandFeature = async (featureId: string) => {
    if (expandedFeature === featureId) {
      setExpandedFeature(null);
      setFeatureDocuments(null);
      return;
    }

    setExpandedFeature(featureId);
    setLoadingDocs(true);

    try {
      const response = await fetch(`/api/features/${featureId}`);
      const data = await response.json();

      if (data.success) {
        setFeatureDocuments({
          prds: data.prds,
          figmas: data.figmas,
        });
      }
    } catch (err) {
      console.error('Failed to load feature documents:', err);
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleSelectFeature = (feature: Feature) => {
    if (onSelectFeature) {
      onSelectFeature(feature);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground p-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Loading features...</span>
      </div>
    );
  }

  // Compact mode - just show dropdown-like list
  if (compact) {
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Select Feature</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowCreateForm(!showCreateForm)}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {showCreateForm && (
          <Card className="p-3 space-y-2 border-primary/50">
            <input
              type="text"
              placeholder="Feature name..."
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full px-2 py-1 text-sm border rounded bg-background"
            />
            <input
              type="text"
              placeholder="Keywords (comma-separated)..."
              value={newKeywords}
              onChange={(e) => setNewKeywords(e.target.value)}
              className="w-full px-2 py-1 text-sm border rounded bg-background"
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={handleCreateFeature}
                disabled={creating || !newName.trim() || !newKeywords.trim()}
              >
                {creating ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Check className="h-3 w-3" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCreateForm(false)}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          </Card>
        )}

        <div className="space-y-1 max-h-48 overflow-y-auto">
          {features.length === 0 ? (
            <p className="text-xs text-muted-foreground p-2">
              No features yet. Create one above.
            </p>
          ) : (
            features.map((feature) => (
              <button
                key={feature.id}
                onClick={() => handleSelectFeature(feature)}
                className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                  selectedFeatureId === feature.id
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-muted'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium truncate">{feature.name}</span>
                  <span className="text-xs opacity-75">
                    {feature.prd_count + feature.figma_count} docs
                  </span>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    );
  }

  // Full mode - show full feature management UI
  return (
    <Card className="border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderKanban className="h-4 w-4 text-primary" />
            <span>Features</span>
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {features.length}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={fetchFeatures}>
              <RefreshCw className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setShowCreateForm(!showCreateForm)}
            >
              <Plus className="h-3 w-3" />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>

      <CardContent className="pt-0 space-y-3">
        {error && (
          <div className="text-xs text-destructive bg-destructive/10 p-2 rounded">
            {error}
          </div>
        )}

        {/* Create Form */}
        {showCreateForm && (
          <Card className="p-3 space-y-2 border-primary/50 bg-primary/5">
            <div className="text-xs font-medium text-primary">New Feature</div>
            <input
              type="text"
              placeholder="Feature name (e.g., Subscription Flow)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full px-2 py-1.5 text-sm border rounded bg-background"
            />
            <input
              type="text"
              placeholder="Keywords for codebase linking (e.g., subscription, plan, premium)"
              value={newKeywords}
              onChange={(e) => setNewKeywords(e.target.value)}
              className="w-full px-2 py-1.5 text-sm border rounded bg-background"
            />
            <textarea
              placeholder="Description (optional)"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              className="w-full px-2 py-1.5 text-sm border rounded bg-background resize-none"
              rows={2}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={handleCreateFeature}
                disabled={creating || !newName.trim() || !newKeywords.trim()}
                className="flex-1"
              >
                {creating ? (
                  <>
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Check className="h-3 w-3 mr-1" />
                    Create Feature
                  </>
                )}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setShowCreateForm(false)}>
                <X className="h-3 w-3" />
              </Button>
            </div>
          </Card>
        )}

        {/* Features List */}
        <div className="space-y-2">
          {features.length === 0 ? (
            <div className="text-sm text-muted-foreground text-center py-4">
              No features yet. Create one to group your PRDs and Figma designs.
            </div>
          ) : (
            features.map((feature) => (
              <Card
                key={feature.id}
                className={`overflow-hidden transition-all ${
                  selectedFeatureId === feature.id
                    ? 'border-primary ring-1 ring-primary/20'
                    : 'border-border/50 hover:border-border'
                }`}
              >
                {/* Feature Header */}
                <div
                  className="flex items-center justify-between p-3 cursor-pointer"
                  onClick={() => handleExpandFeature(feature.id)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <ChevronRight
                      className={`h-4 w-4 text-muted-foreground transition-transform ${
                        expandedFeature === feature.id ? 'rotate-90' : ''
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">{feature.name}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        {feature.keywords.slice(0, 3).map((kw, i) => (
                          <span
                            key={i}
                            className="text-[10px] px-1.5 py-0.5 bg-muted rounded text-muted-foreground"
                          >
                            {kw}
                          </span>
                        ))}
                        {feature.keywords.length > 3 && (
                          <span className="text-[10px] text-muted-foreground">
                            +{feature.keywords.length - 3}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="flex items-center gap-3 mr-2">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <FileText className="h-3 w-3" />
                      <span>{feature.prd_count}</span>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Palette className="h-3 w-3" />
                      <span>{feature.figma_count}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectFeature(feature);
                      }}
                    >
                      Select
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteFeature(feature.id);
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>

                {/* Expanded Content */}
                {expandedFeature === feature.id && (
                  <div className="border-t bg-muted/30 p-3 space-y-3">
                    {loadingDocs ? (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Loading documents...
                      </div>
                    ) : (
                      <>
                        {/* PRDs */}
                        <div>
                          <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
                            <FileText className="h-3 w-3" />
                            PRD Documents
                          </div>
                          {featureDocuments?.prds?.length ? (
                            <div className="space-y-1">
                              {featureDocuments.prds.map((doc) => (
                                <div
                                  key={doc.id}
                                  className="flex items-center justify-between px-2 py-1 bg-background rounded text-xs"
                                >
                                  <span className="truncate">{doc.name}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-xs text-muted-foreground">No PRDs linked</div>
                          )}
                        </div>

                        {/* Figmas */}
                        <div>
                          <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
                            <Palette className="h-3 w-3" />
                            Figma Screens
                          </div>
                          {featureDocuments?.figmas?.length ? (
                            <div className="space-y-1">
                              {featureDocuments.figmas.map((doc) => (
                                <div
                                  key={doc.id}
                                  className="flex items-center justify-between px-2 py-1 bg-background rounded text-xs"
                                >
                                  <span className="truncate">{doc.name}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-xs text-muted-foreground">No Figma screens linked</div>
                          )}
                        </div>

                        {/* Codebase Context */}
                        <div>
                          <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground mb-1">
                            <Code2 className="h-3 w-3" />
                            Codebase (auto-linked via keywords)
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {feature.keywords.map((kw, i) => (
                              <span
                                key={i}
                                className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-primary/10 rounded text-primary"
                              >
                                <Tag className="h-2.5 w-2.5" />
                                {kw}
                              </span>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </Card>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
