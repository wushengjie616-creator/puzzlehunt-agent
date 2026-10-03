(function sudokuNavigationModule(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.sudokuNavigationTarget = api.sudokuNavigationTarget;
}(typeof globalThis === "undefined" ? this : globalThis, function buildSudokuNavigation() {
  function sudokuNavigationTarget(row, column, key, size) {
    const moves = {
      ArrowUp: [-1, 0],
      ArrowRight: [0, 1],
      ArrowDown: [1, 0],
      ArrowLeft: [0, -1],
    };
    const move = moves[key];
    if (!move) return null;
    const clamp = value => Math.max(0, Math.min(size - 1, value));
    return [clamp(row + move[0]), clamp(column + move[1])];
  }
  return {sudokuNavigationTarget};
}));
