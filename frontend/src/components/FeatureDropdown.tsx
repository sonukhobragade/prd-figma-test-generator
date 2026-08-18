import { useState, useEffect, useRef } from 'react';
import {
  ChevronDown,
  Check,
  Loader2,
  Monitor,
  Server,
  FileText,
  Palette,
  Image,
  Smartphone,
  Settings,
  type LucideIcon,
} from 'lucide-react';

// Version info within a feature
interface FeatureVersion {
  version: number;
  session_id: string;
  documents_included: string[];
  frontend_count: number;
  backend_count: number;
  last_updated: string;
}

// Feature structure from /api/rag/features
interface RagFeature {
  feature_name: string;
  versions: FeatureVersion[];
}

// Simplified feature interface for the dropdown selection
export interface Feature {
  id: string;
  name: string;
  keywords: string[];
  description: string;
  prd_count: number;
  figma_count: number;
  // New fields from RAG
  versions?: FeatureVersion[];
  total_frontend: number;
  total_backend: number;
}

interface FeatureDropdownProps {
  value: string;
  onChange: (value: string) => void;
  selectedFeature: Feature | null;
  onSelectFeature: (feature: Feature | null) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

// Document badge mapping with SVG icons
const documentBadges: Record<string, { Icon: LucideIcon; label: string; color: string }> = {
  prd: { Icon: FileText, label: 'PRD', color: 'text-blue-600' },
  figma: { Icon: Palette, label: 'Figma', color: 'text-purple-600' },
  screenshot: { Icon: Image, label: 'Screenshot', color: 'text-pink-600' },
  frontend_lld: { Icon: Smartphone, label: 'Frontend', color: 'text-green-600' },
  backend_lld: { Icon: Settings, label: 'Backend', color: 'text-orange-600' },
};

export function FeatureDropdown({
  value,
  onChange,
  selectedFeature,
  onSelectFeature,
  placeholder = 'Type feature name or select existing...',
  className = '',
  disabled = false,
}: FeatureDropdownProps) {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch features on mount
  useEffect(() => {
    fetchFeatures();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchFeatures = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/rag/features');
      const data = await response.json();

      if (data.success && data.features) {
        // Transform RAG features to dropdown format
        const transformedFeatures: Feature[] = data.features.map((ragFeature: RagFeature) => {
          const totalFrontend = ragFeature.versions.reduce((sum, v) => sum + v.frontend_count, 0);
          const totalBackend = ragFeature.versions.reduce((sum, v) => sum + v.backend_count, 0);
          const allDocs = new Set<string>();
          ragFeature.versions.forEach(v => v.documents_included.forEach(d => allDocs.add(d)));

          return {
            id: ragFeature.feature_name.replace(/\s+/g, '_'),
            name: ragFeature.feature_name,
            keywords: Array.from(allDocs),
            description: `${ragFeature.versions.length} version(s)`,
            prd_count: totalFrontend,
            figma_count: totalBackend,
            versions: ragFeature.versions,
            total_frontend: totalFrontend,
            total_backend: totalBackend,
          };
        });
        setFeatures(transformedFeatures);
      }
    } catch (err) {
      console.error('Failed to fetch features:', err);
    } finally {
      setLoading(false);
    }
  };

  // Filter features based on input
  const filteredFeatures = features.filter(f =>
    f.name.toLowerCase().includes(value.toLowerCase())
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    onChange(newValue);
    // Clear selection if user is typing something different
    if (selectedFeature && newValue !== selectedFeature.name) {
      onSelectFeature(null);
    }
    setIsOpen(true);
  };

  const handleSelect = (feature: Feature) => {
    onChange(feature.name);
    onSelectFeature(feature);
    setIsOpen(false);
    inputRef.current?.blur();
  };

  const handleInputFocus = () => {
    setIsOpen(true);
  };

  const handleInputBlur = () => {
    // Delay closing to allow click on dropdown items
    setTimeout(() => {
      if (!dropdownRef.current?.contains(document.activeElement)) {
        setIsOpen(false);
      }
    }, 150);
  };

  const showDropdown = isOpen && (filteredFeatures.length > 0 || loading);

  return (
    <div ref={dropdownRef} className={`relative ${className}`}>
      {/* Combined Input with Dropdown */}
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onBlur={handleInputBlur}
          placeholder={placeholder}
          disabled={disabled}
          className={`
            w-full px-3 py-2 pr-8 text-sm
            border rounded-md bg-background
            transition-colors
            focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary
            disabled:opacity-50 disabled:cursor-not-allowed
            ${selectedFeature ? 'border-green-400 bg-green-50/30' : 'border-input'}
          `}
        />
        <button
          type="button"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          disabled={disabled}
        >
          <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Selected feature indicator */}
      {selectedFeature && (
        <div className="flex items-center gap-2 mt-1.5 text-xs text-green-600">
          <Check className="h-3 w-3" />
          <span>Existing feature selected</span>
          <span className="text-muted-foreground">•</span>
          <span className="flex items-center gap-1">
            <Monitor className="h-3 w-3" /> {selectedFeature.total_frontend}
          </span>
          {selectedFeature.total_backend > 0 && (
            <span className="flex items-center gap-1">
              <Server className="h-3 w-3" /> {selectedFeature.total_backend}
            </span>
          )}
        </div>
      )}

      {/* Dropdown Menu */}
      {showDropdown && (
        <div
          className="absolute z-50 top-full left-0 right-0 mt-1 bg-popover border rounded-md shadow-lg overflow-hidden max-h-64 overflow-y-auto"
          style={{ backgroundColor: 'hsl(var(--background))' }}
        >
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : filteredFeatures.length === 0 ? (
            <div className="px-3 py-3 text-xs text-muted-foreground text-center">
              <p>No matching features found.</p>
              <p className="mt-1 text-foreground font-medium">"{value}" will be created as new</p>
            </div>
          ) : (
            <>
              {value && !filteredFeatures.some(f => f.name.toLowerCase() === value.toLowerCase()) && (
                <div className="px-3 py-2 text-xs text-muted-foreground border-b bg-muted/30">
                  Press Enter to create "<span className="font-medium text-foreground">{value}</span>" as new feature
                </div>
              )}
              {filteredFeatures.map((feature) => (
                <button
                  key={feature.id}
                  type="button"
                  onClick={() => handleSelect(feature)}
                  className={`
                    w-full flex items-center justify-between px-3 py-2.5 text-sm text-left
                    transition-colors hover:bg-muted/50 border-b border-border/30 last:border-0
                    ${selectedFeature?.id === feature.id ? 'bg-primary/10' : ''}
                  `}
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-foreground truncate">{feature.name}</div>
                    {/* Document badges */}
                    <div className="flex items-center gap-1 mt-1">
                      {feature.keywords.slice(0, 4).map((doc, i) => {
                        const badge = documentBadges[doc];
                        if (!badge) return null;
                        const { Icon, color } = badge;
                        return (
                          <span key={i} title={badge.label}>
                            <Icon className={`h-3 w-3 ${color}`} />
                          </span>
                        );
                      })}
                      {feature.versions && (
                        <span className="text-[10px] text-muted-foreground ml-1">
                          {feature.versions.length}v
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-2">
                    <div className="flex flex-col items-end gap-0.5 text-[10px]">
                      <span className="flex items-center gap-1 text-blue-600">
                        <Monitor className="h-3 w-3" />
                        {feature.total_frontend}
                      </span>
                      {feature.total_backend > 0 && (
                        <span className="flex items-center gap-1 text-green-600">
                          <Server className="h-3 w-3" />
                          {feature.total_backend}
                        </span>
                      )}
                    </div>
                    {selectedFeature?.id === feature.id && (
                      <Check className="h-4 w-4 text-primary" />
                    )}
                  </div>
                </button>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
