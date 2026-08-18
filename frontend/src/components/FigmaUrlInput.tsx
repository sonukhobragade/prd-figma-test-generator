import { useState } from 'react';
import { Link, AlertCircle, CheckCircle } from 'lucide-react';

interface FigmaUrlInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function FigmaUrlInput({ value, onChange }: FigmaUrlInputProps) {
  const [isValid, setIsValid] = useState<boolean | null>(null);

  const validateFigmaUrl = (url: string): boolean => {
    if (!url) return false;
    try {
      const urlObj = new URL(url);
      return urlObj.hostname === 'www.figma.com' || urlObj.hostname === 'figma.com';
    } catch {
      return false;
    }
  };

  const handleChange = (newValue: string) => {
    onChange(newValue);
    if (newValue.trim()) {
      setIsValid(validateFigmaUrl(newValue));
    } else {
      setIsValid(null);
    }
  };

  return (
    <div className="w-full">
      <label htmlFor="figma-url" className="block text-sm font-medium text-gray-700 mb-2">
        Figma URL
      </label>
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Link className="h-5 w-5 text-gray-400" />
        </div>
        <input
          id="figma-url"
          type="url"
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="https://figma.com/design/abc123/MyApp?node-id=1-2"
          className={`
            block w-full pl-10 pr-10 py-3 border rounded-lg focus:ring-2 focus:ring-offset-0
            ${isValid === false ? 'border-red-300 focus:ring-red-500 focus:border-red-500' :
              isValid === true ? 'border-green-300 focus:ring-green-500 focus:border-green-500' :
              'border-gray-300 focus:ring-blue-500 focus:border-blue-500'}
          `}
        />
        {isValid !== null && (
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            {isValid ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <AlertCircle className="h-5 w-5 text-red-500" />
            )}
          </div>
        )}
      </div>

      {isValid === false && (
        <p className="mt-2 text-sm text-red-600">
          Please enter a valid Figma URL (e.g., https://figma.com/design/...)
        </p>
      )}

      {isValid === true && (
        <p className="mt-2 text-sm text-green-600">
          Valid Figma URL ✓
        </p>
      )}
    </div>
  );
}
