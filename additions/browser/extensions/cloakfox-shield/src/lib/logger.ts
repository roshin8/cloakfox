/**
 * Logger utility with configurable log levels
 *
 * Provides consistent logging across the extension with:
 * - Log levels (debug, info, warn, error)
 * - Automatic prefixing with component names
 * - Development/production mode awareness
 * - Structured logging support
 */

import { LOG_PREFIX } from '@/constants';

/**
 * Log levels in order of severity
 */
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4,
}

/**
 * Log level names for display
 */
const LOG_LEVEL_NAMES: Record<LogLevel, string> = {
  [LogLevel.DEBUG]: 'DEBUG',
  [LogLevel.INFO]: 'INFO',
  [LogLevel.WARN]: 'WARN',
  [LogLevel.ERROR]: 'ERROR',
  [LogLevel.NONE]: 'NONE',
};

/**
 * Current log level - can be changed at runtime
 * In production, default to WARN to reduce console noise
 */
let currentLogLevel: LogLevel =
  process.env.NODE_ENV === 'production' ? LogLevel.WARN : LogLevel.DEBUG;

/**
 * Set the current log level
 */
export function setLogLevel(level: LogLevel): void {
  currentLogLevel = level;
}

/**
 * Get the current log level
 */
export function getLogLevel(): LogLevel {
  return currentLogLevel;
}

/**
 * Format a log message with timestamp and component
 */
function formatMessage(component: string, message: string): string {
  return `${LOG_PREFIX} [${component}] ${message}`;
}

/**
 * Logger class for a specific component
 */
export class Logger {
  private component: string;

  constructor(component: string) {
    this.component = component;
  }

  /**
   * Log a debug message (most verbose)
   */
  debug(message: string, ...args: unknown[]): void {
    if (currentLogLevel <= LogLevel.DEBUG) {
      console.debug(formatMessage(this.component, message), ...args);
    }
  }

  /**
   * Log an info message
   */
  info(message: string, ...args: unknown[]): void {
    if (currentLogLevel <= LogLevel.INFO) {
      console.info(formatMessage(this.component, message), ...args);
    }
  }

  /**
   * Log a warning message
   */
  warn(message: string, ...args: unknown[]): void {
    if (currentLogLevel <= LogLevel.WARN) {
      console.warn(formatMessage(this.component, message), ...args);
    }
  }

  /**
   * Log an error message
   */
  error(message: string, ...args: unknown[]): void {
    if (currentLogLevel <= LogLevel.ERROR) {
      console.error(formatMessage(this.component, message), ...args);
    }
  }

  /**
   * Log with explicit level
   */
  log(level: LogLevel, message: string, ...args: unknown[]): void {
    switch (level) {
      case LogLevel.DEBUG:
        this.debug(message, ...args);
        break;
      case LogLevel.INFO:
        this.info(message, ...args);
        break;
      case LogLevel.WARN:
        this.warn(message, ...args);
        break;
      case LogLevel.ERROR:
        this.error(message, ...args);
        break;
    }
  }

  /**
   * Create a child logger with a sub-component name
   */
  child(subComponent: string): Logger {
    return new Logger(`${this.component}:${subComponent}`);
  }
}

/**
 * Create a logger for a specific component
 */
export function createLogger(component: string): Logger {
  return new Logger(component);
}

// Pre-created loggers for common components
export const backgroundLogger = createLogger('Background');
export const contentLogger = createLogger('Content');
export const injectLogger = createLogger('Inject');
export const popupLogger = createLogger('Popup');
