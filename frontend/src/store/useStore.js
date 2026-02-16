import { create } from 'zustand';

const useStore = create((set) => ({
  bookmarks: new Set(),
  toggleBookmark: (id) =>
    set((state) => {
      const next = new Set(state.bookmarks);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return { bookmarks: next };
    }),
}));

export default useStore;
