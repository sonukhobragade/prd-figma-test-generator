import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface FileUploadZoneProps {
  onFileSelect: (file: File) => void;
  maxSize?: number;
  disabled?: boolean;
}

export function FileUploadZone({ onFileSelect, maxSize = 50 * 1024 * 1024, disabled = false }: FileUploadZoneProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    setError(null);

    if (rejectedFiles.length > 0) {
      const rejection = rejectedFiles[0];
      if (rejection.errors[0].code === 'file-too-large') {
        setError(`File is too large. Maximum size is ${(maxSize / 1024 / 1024).toFixed(0)}MB`);
      } else {
        setError('Invalid file type. Please upload PDF, PNG, JPG, JPEG, or TXT files.');
      }
      return;
    }

    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      setSelectedFile(file);
      onFileSelect(file);
    }
  }, [onFileSelect, maxSize]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'text/plain': ['.txt'],
    },
    maxSize,
    multiple: false,
    disabled,
  });

  const clearFile = () => {
    setSelectedFile(null);
    setError(null);
  };

  return (
    <div className="w-full">
      <Card>
        <CardContent className="p-0">
          <div
            {...getRootProps()}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center transition-colors
              ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              ${isDragActive && !disabled ? 'border-primary bg-primary/10' : 'border-input'}
              ${!disabled && !isDragActive ? 'hover:border-primary/50' : ''}
              ${error ? 'border-destructive bg-destructive/10' : ''}
            `}
          >
            <input {...getInputProps()} />
            <Upload className={`mx-auto h-12 w-12 mb-4 ${isDragActive ? 'text-primary' : 'text-muted-foreground'}`} />

            {isDragActive ? (
              <p className="text-primary font-medium">Drop the file here...</p>
            ) : (
              <div>
                <p className="text-foreground font-medium mb-2">
                  Drag & drop a PRD file here, or click to browse
                </p>
                <p className="text-sm text-muted-foreground">
                  Supports: PDF, PNG, JPG, JPEG, TXT (Max {(maxSize / 1024 / 1024).toFixed(0)}MB)
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="mt-3 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {selectedFile && !error && (
        <div 
          className="mt-3 p-3 rounded-lg flex items-center justify-between border"
          style={{
            backgroundColor: "hsl(var(--muted))",
            borderColor: "hsl(var(--border))"
          }}
        >
          <div className="flex items-center space-x-3">
            <FileText 
              className="h-5 w-5" 
              style={{ color: "hsl(var(--primary))" }}
            />
            <div>
              <p 
                className="text-sm font-medium"
                style={{ color: "hsl(var(--foreground))" }}
              >
                {selectedFile.name}
              </p>
              <p 
                className="text-xs"
                style={{ color: "hsl(var(--muted-foreground))" }}
              >
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
          <Button
            onClick={(e) => {
              e.stopPropagation();
              clearFile();
            }}
            variant="ghost"
            size="icon"
            className="hover:bg-muted"
            style={{ color: "hsl(var(--muted-foreground))" }}
            disabled={disabled}
          >
            <X className="h-5 w-5" />
          </Button>
        </div>
      )}
    </div>
  );
}
