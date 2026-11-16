// Tracks the newest request so slower, older responses can be dropped.
export function createLatest() {
  let current = 0;
  return {
    next: () => ++current,
    isCurrent: (token) => token === current,
  };
}
