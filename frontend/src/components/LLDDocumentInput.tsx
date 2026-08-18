import { useState } from 'react';
import { FileText, Type, Upload, X, Database, Monitor } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface LLDDocumentInputProps {
  label: string;
  description: string;
  onFileChange: (file: File | null) => void;
  onTextChange: (text: string) => void;
  file: File | null;
  text: string;
  disabled?: boolean;
  type?: 'backend' | 'frontend';
}

export function LLDDocumentInput({
  label,
  description,
  onFileChange,
  onTextChange,
  file,
  text,
  disabled = false,
  type = 'backend',
}: LLDDocumentInputProps) {
  const [inputMode, setInputMode] = useState<'upload' | 'text' | null>(null);

  const hasContent = file !== null || text.trim().length > 0;
  const TypeIcon = type === 'backend' ? Database : Monitor;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      onFileChange(e.target.files[0]);
      onTextChange(''); // Clear text when file is selected
    }
  };

  const clearFile = () => {
    onFileChange(null);
    setInputMode(null);
  };

  const clearText = () => {
    onTextChange('');
    setInputMode(null);
  };

  return (
    <div className="border border-border rounded-xl overflow-hidden bg-card">
      {/* Header */}
      <div className="p-4 border-b border-border/50 bg-muted/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${type === 'backend' ? 'bg-violet-100' : 'bg-blue-100'}`}>
              <TypeIcon className={`h-5 w-5 ${type === 'backend' ? 'text-violet-600' : 'text-blue-600'}`} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-foreground">{label}</span>
                <span className="text-xs px-2 py-0.5 bg-muted text-muted-foreground rounded-full">
                  Optional
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
            </div>
          </div>
          {hasContent && (
            <span className="text-xs px-2.5 py-1 bg-primary/10 text-primary rounded-full flex items-center gap-1.5 font-medium">
              <FileText className="h-3 w-3" />
              {file ? 'PDF Added' : 'Text Added'}
            </span>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="p-4">
        {/* Show buttons if no content yet */}
        {!hasContent && inputMode === null && (
          <div className="flex gap-3">
            <Button
              type="button"
              onClick={() => setInputMode('upload')}
              disabled={disabled}
              variant="outline"
              className="flex-1 h-12 flex items-center justify-center gap-2 hover:bg-primary/5 hover:border-primary/50"
            >
              <Upload className="h-5 w-5" />
              <span>Upload PDF</span>
            </Button>
            <Button
              type="button"
              onClick={() => setInputMode('text')}
              disabled={disabled}
              variant="outline"
              className="flex-1 h-12 flex items-center justify-center gap-2 hover:bg-primary/5 hover:border-primary/50"
            >
              <Type className="h-5 w-5" />
              <span>Paste Text</span>
            </Button>
          </div>
        )}

        {/* Upload Mode */}
        {(inputMode === 'upload' || file) && (
          <div>
            {file ? (
              <div className="flex items-center justify-between p-3 border border-primary/30 rounded-lg bg-primary/5">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  <span className="text-sm font-medium text-foreground">{file.name}</span>
                  <span className="text-xs text-muted-foreground">
                    ({(file.size / 1024).toFixed(1)} KB)
                  </span>
                </div>
                <Button
                  type="button"
                  onClick={clearFile}
                  disabled={disabled}
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <label
                  className={`flex flex-col items-center justify-center p-6 border-2 border-dashed border-input rounded-lg cursor-pointer transition-colors ${
                    disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-primary hover:bg-primary/5'
                  }`}
                >
                  <Upload className="h-8 w-8 text-muted-foreground mb-2" />
                  <span className="text-sm font-medium text-foreground">
                    Drop PDF here or click to browse
                  </span>
                  <span className="text-xs text-muted-foreground mt-1">
                    Supports PDF, TXT, MD files
                  </span>
                  <input
                    type="file"
                    accept=".pdf,.txt,.md"
                    onChange={handleFileSelect}
                    disabled={disabled}
                    className="hidden"
                  />
                </label>
                <Button
                  type="button"
                  onClick={() => setInputMode(null)}
                  disabled={disabled}
                  variant="ghost"
                  size="sm"
                  className="w-full text-muted-foreground"
                >
                  Cancel
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Text Mode */}
        {(inputMode === 'text' || (text.trim().length > 0 && !file)) && !file && (
          <div className="space-y-3">
            <Textarea
              value={text}
              onChange={(e) => onTextChange(e.target.value)}
              placeholder={`Paste your ${label} content here...\n\n${
                type === 'backend'
                  ? 'Include:\n- API endpoints (routes, methods)\n- Database schema (tables, columns)\n- Request/response examples\n- Error codes'
                  : 'Include:\n- Screen routes\n- Component hierarchy\n- State management\n- UI behaviors'
              }`}
              disabled={disabled}
              className="h-40 font-mono text-sm resize-y"
            />
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {text.length > 0 ? (
                  <span className="text-primary font-medium">
                    {text.length} characters
                  </span>
                ) : (
                  'Paste content to enable test generation'
                )}
              </p>
              <div className="flex gap-2">
                {!text.trim() && (
                  <Button
                    type="button"
                    onClick={() => setInputMode(null)}
                    disabled={disabled}
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground"
                  >
                    Cancel
                  </Button>
                )}
                {text.length > 0 && !disabled && (
                  <Button
                    type="button"
                    onClick={clearText}
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                  >
                    Clear
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
