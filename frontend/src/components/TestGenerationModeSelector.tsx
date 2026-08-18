import { Server, Monitor } from 'lucide-react';
import { Button } from '@/components/ui/button';

export type TestGenerationMode = 'frontend' | 'backend';

interface TestGenerationModeSelectorProps {
  mode: TestGenerationMode;
  onModeChange: (mode: TestGenerationMode) => void;
  disabled?: boolean;
}

export function TestGenerationModeSelector({
  mode,
  onModeChange,
  disabled = false,
}: TestGenerationModeSelectorProps) {
  return (
    <div className="w-full">
      <label className="block text-sm font-medium text-foreground mb-2">
        Test Generation Mode
      </label>
      <div className="flex rounded-lg border border-border p-1 bg-muted/30">
        <Button
          type="button"
          onClick={() => onModeChange('frontend')}
          disabled={disabled}
          variant={mode === 'frontend' ? 'default' : 'ghost'}
          className={`
            flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-md transition-all
            ${mode === 'frontend'
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'hover:bg-muted text-muted-foreground'
            }
          `}
        >
          <Monitor className="h-4 w-4" />
          <span className="font-medium">Frontend Tests</span>
        </Button>
        <Button
          type="button"
          onClick={() => onModeChange('backend')}
          disabled={disabled}
          variant={mode === 'backend' ? 'default' : 'ghost'}
          className={`
            flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-md transition-all
            ${mode === 'backend'
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'hover:bg-muted text-muted-foreground'
            }
          `}
        >
          <Server className="h-4 w-4" />
          <span className="font-medium">Backend Tests</span>
        </Button>
      </div>
    </div>
  );
}
