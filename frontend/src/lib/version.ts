function parseVersion(value: string | null | undefined): number[] | null {
  if (!value) return null;
  const normalized = value.trim().replace(/^[vV]/, '').split(/[-+]/, 1)[0];
  const parts = normalized.split('.');
  if (parts.length < 1 || parts.length > 3 || parts.some((part) => !/^\d+$/.test(part))) {
    return null;
  }
  return [...parts.map(Number), 0, 0].slice(0, 3);
}

export function isVersionOlder(current: string | null | undefined, latest: string | null | undefined): boolean {
  const currentParts = parseVersion(current);
  const latestParts = parseVersion(latest);
  if (!currentParts || !latestParts) return false;
  for (let index = 0; index < latestParts.length; index += 1) {
    if (currentParts[index] !== latestParts[index]) {
      return currentParts[index] < latestParts[index];
    }
  }
  return false;
}