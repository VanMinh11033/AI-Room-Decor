import type { InputHTMLAttributes } from "react";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  const { className = "", ...rest } = props;
  return <input className={`w-full rounded-md border border-black/15 bg-white px-3 py-2 text-sm ${className}`} {...rest} />;
}

