/**
 * Phoenix Guardian - Language Switcher Component
 * Week 31-32: Multi-Language Support for Clinical Documentation
 * 
 * Provides language selection for LEP (Limited English Proficient) patients
 * Supports: English (en-US), Spanish (es-MX, es-US), Mandarin Chinese (zh-CN)
 */

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';

// ============================================================================
// Type Definitions
// ============================================================================

export type LanguageCode = 'en-US' | 'es-MX' | 'es-US' | 'zh-CN';

export interface Language {
  code: LanguageCode;
  name: string;
  nativeName: string;
  flag: string;
  direction: 'ltr' | 'rtl';
  medicalSupport: boolean;
  speechRecognition: boolean;
}

export interface LanguageSwitcherProps {
  /** Current selected language */
  currentLanguage: LanguageCode;
  /** Callback when language is changed */
  onLanguageChange: (language: LanguageCode) => void;
  /** Display variant */
  variant?: 'dropdown' | 'buttons' | 'compact';
  /** Show native language names */
  showNativeNames?: boolean;
  /** Show language flags */
  showFlags?: boolean;
  /** Disabled state */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Aria label for accessibility */
  ariaLabel?: string;
  /** Context: 'ui' for interface, 'patient' for patient language selection */
  context?: 'ui' | 'patient';
}

// ============================================================================
// Supported Languages Configuration
// ============================================================================

export const SUPPORTED_LANGUAGES: Language[] = [
  {
    code: 'en-US',
    name: 'English',
    nativeName: 'English',
    flag: '🇺🇸',
    direction: 'ltr',
    medicalSupport: true,
    speechRecognition: true,
  },
  {
    code: 'es-MX',
    name: 'Spanish (Mexico)',
    nativeName: 'Español (México)',
    flag: '🇲🇽',
    direction: 'ltr',
    medicalSupport: true,
    speechRecognition: true,
  },
  {
    code: 'es-US',
    name: 'Spanish (US)',
    nativeName: 'Español (EE.UU.)',
    flag: '🇺🇸',
    direction: 'ltr',
    medicalSupport: true,
    speechRecognition: true,
  },
  {
    code: 'zh-CN',
    name: 'Mandarin Chinese',
    nativeName: '普通话',
    flag: '🇨🇳',
    direction: 'ltr',
    medicalSupport: true,
    speechRecognition: true,
  },
];

// ============================================================================
// Utility Functions
// ============================================================================

export const getLanguageByCode = (code: LanguageCode): Language | undefined => {
  return SUPPORTED_LANGUAGES.find((lang) => lang.code === code);
};

export const getDisplayName = (
  language: Language,
  showNative: boolean = false
): string => {
  return showNative ? `${language.name} (${language.nativeName})` : language.name;
};

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook for managing language state with localStorage persistence
 */
export const useLanguage = (defaultLanguage: LanguageCode = 'en-US') => {
  const [language, setLanguage] = useState<LanguageCode>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('phoenix_guardian_language');
      if (stored && SUPPORTED_LANGUAGES.some((l) => l.code === stored)) {
        return stored as LanguageCode;
      }
    }
    return defaultLanguage;
  });

  const changeLanguage = useCallback((newLanguage: LanguageCode) => {
    setLanguage(newLanguage);
    if (typeof window !== 'undefined') {
      localStorage.setItem('phoenix_guardian_language', newLanguage);
      // Dispatch event for other components to react
      window.dispatchEvent(
        new CustomEvent('languageChange', { detail: { language: newLanguage } })
      );
    }
  }, []);

  return { language, changeLanguage };
};

// ============================================================================
// Sub-Components
// ============================================================================

interface LanguageOptionProps {
  language: Language;
  isSelected: boolean;
  showNativeNames: boolean;
  showFlags: boolean;
  onClick: () => void;
  disabled?: boolean;
}

const LanguageOption: React.FC<LanguageOptionProps> = ({
  language,
  isSelected,
  showNativeNames,
  showFlags,
  onClick,
  disabled,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`
        language-option
        ${isSelected ? 'language-option--selected' : ''}
        ${disabled ? 'language-option--disabled' : ''}
      `}
      role="option"
      aria-selected={isSelected}
      aria-disabled={disabled}
    >
      {showFlags && <span className="language-option__flag">{language.flag}</span>}
      <span className="language-option__name">
        {showNativeNames ? language.nativeName : language.name}
      </span>
      {!language.medicalSupport && (
        <span className="language-option__badge" title="Limited medical terminology support">
          ⚠️
        </span>
      )}
      {isSelected && <span className="language-option__check">✓</span>}
    </button>
  );
};

// ============================================================================
// Main Component: Dropdown Variant
// ============================================================================

const DropdownLanguageSwitcher: React.FC<LanguageSwitcherProps> = ({
  currentLanguage,
  onLanguageChange,
  showNativeNames = true,
  showFlags = true,
  disabled = false,
  className = '',
  ariaLabel = 'Select language',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentLang = useMemo(
    () => getLanguageByCode(currentLanguage),
    [currentLanguage]
  );

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case 'Escape':
          setIsOpen(false);
          break;
        case 'Enter':
        case ' ':
          setIsOpen((prev) => !prev);
          break;
        case 'ArrowDown':
          if (!isOpen) setIsOpen(true);
          break;
      }
    },
    [isOpen]
  );

  const handleSelect = useCallback(
    (code: LanguageCode) => {
      onLanguageChange(code);
      setIsOpen(false);
    },
    [onLanguageChange]
  );

  return (
    <div
      ref={dropdownRef}
      className={`language-switcher language-switcher--dropdown ${className}`}
    >
      <button
        type="button"
        className="language-switcher__trigger"
        onClick={() => setIsOpen((prev) => !prev)}
        onKeyDown={handleKeyDown}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        disabled={disabled}
      >
        {showFlags && currentLang && (
          <span className="language-switcher__flag">{currentLang.flag}</span>
        )}
        <span className="language-switcher__current">
          {currentLang
            ? showNativeNames
              ? currentLang.nativeName
              : currentLang.name
            : 'Select language'}
        </span>
        <span className="language-switcher__arrow">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div
          className="language-switcher__dropdown"
          role="listbox"
          aria-label="Available languages"
        >
          {SUPPORTED_LANGUAGES.map((language) => (
            <LanguageOption
              key={language.code}
              language={language}
              isSelected={language.code === currentLanguage}
              showNativeNames={showNativeNames}
              showFlags={showFlags}
              onClick={() => handleSelect(language.code)}
              disabled={disabled}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Main Component: Buttons Variant
// ============================================================================

const ButtonsLanguageSwitcher: React.FC<LanguageSwitcherProps> = ({
  currentLanguage,
  onLanguageChange,
  showNativeNames = false,
  showFlags = true,
  disabled = false,
  className = '',
  ariaLabel = 'Select language',
}) => {
  return (
    <div
      className={`language-switcher language-switcher--buttons ${className}`}
      role="radiogroup"
      aria-label={ariaLabel}
    >
      {SUPPORTED_LANGUAGES.map((language) => (
        <button
          key={language.code}
          type="button"
          className={`
            language-button
            ${language.code === currentLanguage ? 'language-button--active' : ''}
          `}
          onClick={() => onLanguageChange(language.code)}
          disabled={disabled}
          role="radio"
          aria-checked={language.code === currentLanguage}
          title={getDisplayName(language, true)}
        >
          {showFlags && <span className="language-button__flag">{language.flag}</span>}
          <span className="language-button__code">
            {showNativeNames ? language.nativeName : language.code.split('-')[0].toUpperCase()}
          </span>
        </button>
      ))}
    </div>
  );
};

// ============================================================================
// Main Component: Compact Variant
// ============================================================================

const CompactLanguageSwitcher: React.FC<LanguageSwitcherProps> = ({
  currentLanguage,
  onLanguageChange,
  disabled = false,
  className = '',
  ariaLabel = 'Select language',
}) => {
  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      onLanguageChange(event.target.value as LanguageCode);
    },
    [onLanguageChange]
  );

  return (
    <div className={`language-switcher language-switcher--compact ${className}`}>
      <select
        value={currentLanguage}
        onChange={handleChange}
        disabled={disabled}
        aria-label={ariaLabel}
        className="language-switcher__select"
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <option key={language.code} value={language.code}>
            {language.flag} {language.nativeName}
          </option>
        ))}
      </select>
    </div>
  );
};

// ============================================================================
// Main Component Export
// ============================================================================

/**
 * Language Switcher Component
 * 
 * Supports three variants:
 * - dropdown: Full dropdown with flags and native names
 * - buttons: Horizontal button group
 * - compact: Simple select element
 * 
 * @example
 * // Dropdown variant (default)
 * <LanguageSwitcher
 *   currentLanguage="en-US"
 *   onLanguageChange={(lang) => setLanguage(lang)}
 * />
 * 
 * @example
 * // Button group for toolbar
 * <LanguageSwitcher
 *   variant="buttons"
 *   currentLanguage="es-MX"
 *   onLanguageChange={(lang) => setLanguage(lang)}
 * />
 * 
 * @example
 * // Compact for mobile
 * <LanguageSwitcher
 *   variant="compact"
 *   currentLanguage="zh-CN"
 *   onLanguageChange={(lang) => setLanguage(lang)}
 * />
 */
export const LanguageSwitcher: React.FC<LanguageSwitcherProps> = (props) => {
  const { variant = 'dropdown' } = props;

  switch (variant) {
    case 'buttons':
      return <ButtonsLanguageSwitcher {...props} />;
    case 'compact':
      return <CompactLanguageSwitcher {...props} />;
    case 'dropdown':
    default:
      return <DropdownLanguageSwitcher {...props} />;
  }
};

// ============================================================================
// CSS Styles (to be imported separately or included in a CSS file)
// ============================================================================

export const languageSwitcherStyles = `
.language-switcher {
  position: relative;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Dropdown Variant */
.language-switcher--dropdown {
  min-width: 180px;
}

.language-switcher__trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  width: 100%;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.language-switcher__trigger:hover {
  border-color: #3b82f6;
}

.language-switcher__trigger:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.language-switcher__trigger:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
  opacity: 0.6;
}

.language-switcher__flag {
  font-size: 20px;
}

.language-switcher__current {
  flex: 1;
  text-align: left;
}

.language-switcher__arrow {
  font-size: 10px;
  color: #6b7280;
}

.language-switcher__dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  z-index: 50;
  max-height: 300px;
  overflow-y: auto;
}

/* Language Option */
.language-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  width: 100%;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  text-align: left;
  transition: background 0.15s;
}

.language-option:hover {
  background: #f3f4f6;
}

.language-option--selected {
  background: #eff6ff;
}

.language-option--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.language-option__flag {
  font-size: 18px;
}

.language-option__name {
  flex: 1;
}

.language-option__badge {
  font-size: 12px;
}

.language-option__check {
  color: #3b82f6;
  font-weight: bold;
}

/* Buttons Variant */
.language-switcher--buttons {
  display: flex;
  gap: 4px;
}

.language-button {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
}

.language-button:hover {
  background: #f3f4f6;
}

.language-button--active {
  background: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

.language-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.language-button__flag {
  font-size: 16px;
}

/* Compact Variant */
.language-switcher--compact {
  display: inline-block;
}

.language-switcher__select {
  padding: 6px 24px 6px 8px;
  font-size: 14px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-position: right 4px center;
  background-repeat: no-repeat;
  background-size: 16px;
}

.language-switcher__select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.language-switcher__select:disabled {
  background-color: #f3f4f6;
  cursor: not-allowed;
}
`;

export default LanguageSwitcher;
