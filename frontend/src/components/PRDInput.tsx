import { useState } from 'react';
import { FileUploadZone } from './FileUploadZone';
import { FileText, Type, Lightbulb } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface PRDInputProps {
  onFileSelect: (file: File | null) => void;
  onTextChange: (text: string) => void;
  selectedFile: File | null;
  textContent: string;
}

export function PRDInput({ onFileSelect, onTextChange, selectedFile: _selectedFile, textContent }: PRDInputProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'text'>('upload');

  const handleTabChange = (tab: 'upload' | 'text') => {
    setActiveTab(tab);
    // Clear the other input when switching tabs
    if (tab === 'upload') {
      onTextChange('');
    } else {
      onFileSelect(null);
    }
  };

  return (
    <div className="w-full">
      {/* Tab Headers */}
      <div className="flex border-b border-border mb-4">
        <Button
          onClick={() => handleTabChange('upload')}
          variant={activeTab === 'upload' ? 'default' : 'ghost'}
          className={`
            flex items-center px-4 py-2 font-medium text-sm border-b-2 rounded-none transition-colors
            ${
              activeTab === 'upload'
                ? 'border-primary'
                : 'border-transparent'
            }
          `}
        >
          <FileText className="h-4 w-4 mr-2" />
          Upload File
        </Button>
        <Button
          onClick={() => handleTabChange('text')}
          variant={activeTab === 'text' ? 'default' : 'ghost'}
          className={`
            flex items-center px-4 py-2 font-medium text-sm border-b-2 rounded-none transition-colors
            ${
              activeTab === 'text'
                ? 'border-primary'
                : 'border-transparent'
            }
          `}
        >
          <Type className="h-4 w-4 mr-2" />
          Paste Text
        </Button>
      </div>

      {/* Tab Content */}
      <div className="mt-4">
        {activeTab === 'upload' ? (
          <FileUploadZone onFileSelect={onFileSelect} />
        ) : (
          <div>
            <textarea
              value={textContent}
              onChange={(e) => onTextChange(e.target.value)}
              placeholder="Paste your PRD content here...&#10;&#10;You can paste plain text, markdown, or any text-based PRD content.&#10;&#10;Example:&#10;# Feature: User Login&#10;## Requirements&#10;- Users must be able to login with email and password&#10;- Password must be at least 8 characters&#10;- Show error messages for invalid credentials"
              className="w-full h-64 px-4 py-3 border border-input rounded-lg focus:ring-2 focus:ring-ring focus:border-ring text-sm font-mono resize-y bg-background text-foreground"
              style={{ minHeight: '200px' }}
            />
            <div className="mt-2 flex items-center justify-between text-sm">
              <p className="text-muted-foreground">
                {textContent.length > 0 ? (
                  <span className="text-green-600 font-medium">
                    {textContent.length} characters
                  </span>
                ) : (
                  'Enter or paste your PRD text content'
                )}
              </p>
              {textContent.length > 0 && (
                <Button
                  onClick={() => onTextChange('')}
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:text-red-800 font-medium"
                >
                  Clear
                </Button>
              )}
            </div>
            <p className="mt-2 text-xs text-muted-foreground flex items-start gap-2">
              <Lightbulb className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
              <span><strong>Tip:</strong> This supports plain text, markdown, and formatted PRD documents. The more detailed your PRD, the better the test case generation.</span>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
