const PALETTE = [
  "bg-tertiary-container text-on-tertiary",
  "bg-primary-container text-on-primary-container",
  "bg-secondary text-secondary-foreground",
  "bg-surface-container-high text-on-surface",
];

export function avatarInitials(name: string | null, phone: string): string {
  if (name) {
    const parts = name.trim().split(/\s+/);
    return parts.length > 1
      ? (parts[0][0] + parts[1][0]).toUpperCase()
      : name.slice(0, 2).toUpperCase();
  }
  return `+${phone.slice(-2)}`;
}

export function avatarColor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}
