import React from "react";

export interface FormFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  helperText?: string;
  required?: boolean;
}

export const FormField = React.forwardRef<HTMLInputElement, FormFieldProps>(
  ({ id, label, error, helperText, required, className = "", ...rest }, ref) => {
    const inputId = id || `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
    const errorId = `${inputId}-error`;
    const helperId = `${inputId}-helper`;

    return (
      <div className="space-y-1.5 w-full">
        <div className="flex items-center justify-between">
          <label htmlFor={inputId} className="block text-xs font-bold uppercase tracking-wider text-[#242B23]">
            {label}
            {required && <span className="ml-1 text-[#B3261E]">*</span>}
          </label>
        </div>

        <input
          ref={ref}
          id={inputId}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          className={`premium-input w-full ${
            error ? "border-[#B3261E] focus:border-[#B3261E] focus:ring-[#B3261E]/20" : ""
          } ${className}`}
          {...rest}
        />

        {error && (
          <p id={errorId} role="alert" className="text-xs font-semibold text-[#B3261E]">
            {error}
          </p>
        )}

        {helperText && !error && (
          <p id={helperId} className="text-xs text-[#5A6258]">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

FormField.displayName = "FormField";
