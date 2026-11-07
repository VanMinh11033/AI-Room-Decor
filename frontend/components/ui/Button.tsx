import type { ButtonHTMLAttributes } from "react";

export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  const { className = "", ...rest } = props;
  return (
    <button
      className={`rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-black disabled:opacity-50 ${className}`}
      {...rest}
    />
  );
}

