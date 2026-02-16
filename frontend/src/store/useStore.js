import { create } from 'zustand';

const useStore = create((set, get) => ({
  // --- Bookmarks ---
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

  // --- Reels / Feed ---
  reels: [],
  feedPage: 1,
  hasMore: true,
  setReels: (reels) => set({ reels }),
  appendReels: (newReels) =>
    set((state) => ({
      reels: [...state.reels, ...newReels],
      feedPage: state.feedPage + 1,
      hasMore: newReels.length > 0,
    })),

  // --- Upload ---
  currentUpload: null, // { id, status, progress }
  setUploadStatus: (upload) => set({ currentUpload: upload }),
  clearUpload: () => set({ currentUpload: null }),

  // --- Onboarding Preferences ---
  preferences: null,
  onboardingCompleted: false,
  setPreferences: (prefs) => set({ preferences: prefs, onboardingCompleted: true }),
  clearPreferences: () => set({ preferences: null, onboardingCompleted: false }),
}));

export default useStore;
