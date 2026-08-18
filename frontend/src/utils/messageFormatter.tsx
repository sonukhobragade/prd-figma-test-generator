import type { ReactNode } from 'react';
import {
  Rocket,
  CheckCircle2,
  AlertTriangle,
  Info,
  BarChart3,
  Lightbulb,
  Search,
  Brain,
  Radio,
  Hourglass,
  FileText,
  Palette,
  Image,
  ClipboardList,
  type LucideIcon,
} from 'lucide-react';

/**
 * Icon mapping for message formatting
 * Maps icon identifiers from backend messages to lucide-react components
 */
const ICON_MAP: Record<string, LucideIcon> = {
  ROCKET: Rocket,
  CHECK: CheckCircle2,
  ALERT: AlertTriangle,
  INFO: Info,
  CHART: BarChart3,
  LIGHTBULB: Lightbulb,
  SEARCH: Search,
  BRAIN: Brain,
  RADIO: Radio,
  HOURGLASS: Hourglass,
  FILE: FileText,
  PALETTE: Palette,
  IMAGE: Image,
  CLIPBOARD: ClipboardList,
};

/**
 * Icon color classes for different message types
 */
const ICON_COLORS: Record<string, string> = {
  ROCKET: 'text-blue-400',
  CHECK: 'text-green-400',
  ALERT: 'text-amber-400',
  INFO: 'text-gray-400',
  CHART: 'text-purple-400',
  LIGHTBULB: 'text-yellow-400',
  SEARCH: 'text-blue-400',
  BRAIN: 'text-purple-400',
  RADIO: 'text-cyan-400',
  HOURGLASS: 'text-orange-400',
  FILE: 'text-gray-400',
  PALETTE: 'text-pink-400',
  IMAGE: 'text-indigo-400',
  CLIPBOARD: 'text-teal-400',
};

interface ParsedMessage {
  icon: string | null;
  text: string;
  originalMessage: string;
}

/**
 * Parses a message with icon identifier format: [ICON_NAME] Message text
 *
 * @param message - Message string with optional icon identifier
 * @returns Parsed message object with icon and text separated
 *
 * @example
 * parseMessage("[ROCKET] Starting analysis...")
 * // Returns: { icon: "ROCKET", text: "Starting analysis...", originalMessage: "..." }
 *
 * parseMessage("Plain message")
 * // Returns: { icon: null, text: "Plain message", originalMessage: "..." }
 */
export function parseMessage(message: string): ParsedMessage {
  const iconMatch = message.match(/^\[([A-Z]+)\]\s*(.*)$/);

  if (iconMatch) {
    return {
      icon: iconMatch[1],
      text: iconMatch[2],
      originalMessage: message,
    };
  }

  return {
    icon: null,
    text: message,
    originalMessage: message,
  };
}

interface FormattedMessageProps {
  message: string;
  className?: string;
  iconClassName?: string;
  textClassName?: string;
}

/**
 * Renders a formatted message with icon component
 *
 * @param message - Message string with icon identifier
 * @param className - Additional classes for container
 * @param iconClassName - Additional classes for icon (overrides default color)
 * @param textClassName - Additional classes for text
 *
 * @example
 * <FormattedMessage message="[ROCKET] Starting analysis..." />
 * <FormattedMessage
 *   message="[CHECK] Complete!"
 *   className="font-semibold"
 *   iconClassName="text-green-500"
 * />
 */
export function FormattedMessage({
  message,
  className = '',
  iconClassName,
  textClassName = '',
}: FormattedMessageProps): ReactNode {
  const parsed = parseMessage(message);
  const IconComponent = parsed.icon ? ICON_MAP[parsed.icon] : null;
  const defaultIconColor = parsed.icon ? ICON_COLORS[parsed.icon] : '';

  // If no icon found, render plain text
  if (!IconComponent) {
    return <span className={`${className} ${textClassName}`}>{parsed.text}</span>;
  }

  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <IconComponent
        className={`h-4 w-4 ${iconClassName || defaultIconColor}`}
        aria-hidden="true"
      />
      <span className={textClassName}>{parsed.text}</span>
    </span>
  );
}

/**
 * Extracts just the text from a message, removing icon identifier
 *
 * @param message - Message string with optional icon identifier
 * @returns Plain text without icon identifier
 *
 * @example
 * getMessageText("[ROCKET] Starting analysis...")
 * // Returns: "Starting analysis..."
 */
export function getMessageText(message: string): string {
  return parseMessage(message).text;
}

/**
 * Gets the icon component for a message (without rendering)
 *
 * @param message - Message string with icon identifier
 * @returns Lucide icon component or null if no icon found
 *
 * @example
 * const Icon = getMessageIcon("[ROCKET] Starting...");
 * return Icon ? <Icon className="h-5 w-5" /> : null;
 */
export function getMessageIcon(message: string): LucideIcon | null {
  const parsed = parseMessage(message);
  return parsed.icon ? ICON_MAP[parsed.icon] || null : null;
}

/**
 * Gets the default color class for a message's icon
 *
 * @param message - Message string with icon identifier
 * @returns Tailwind color class string
 */
export function getMessageIconColor(message: string): string {
  const parsed = parseMessage(message);
  return parsed.icon ? ICON_COLORS[parsed.icon] || 'text-gray-400' : 'text-gray-400';
}
