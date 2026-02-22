import { create } from 'zustand';
import { getBookmarks, addBookmark as apiAddBookmark, removeBookmark as apiRemoveBookmark, trackInteraction, getLikedReels, logoutApi } from '../api';
import { clearAudioCache } from '../services/audioCache';

const useStore = create((set, get) => ({
  // --- Auth ---
  user: JSON.parse(localStorage.getItem('verso_user') || 'null'),
  token: localStorage.getItem('verso_token') || null,
  setAuth: (user, token, refreshToken) => {
    localStorage.setItem('verso_user', JSON.stringify(user));
    localStorage.setItem('verso_token', token);
    if (refreshToken) localStorage.setItem('verso_refresh_token', refreshToken);
    set({ user, token });
  },
  logout: () => {
    const refreshToken = localStorage.getItem('verso_refresh_token');
    if (refreshToken) logoutApi(refreshToken);
    localStorage.removeItem('verso_user');
    localStorage.removeItem('verso_token');
    localStorage.removeItem('verso_refresh_token');
    localStorage.removeItem('verso_display_name');
    localStorage.removeItem('verso_user_role');
    localStorage.removeItem('verso_onboarded');
    clearAudioCache();
    set({
      user: null,
      token: null,
      reels: [],
      feedPage: 1,
      hasMore: true,
      bookmarks: new Map(),
      bookmarkItems: [],
      likes: new Map(),
      currentUpload: null,
      bgUpload: null,
      displayName: null,
      userRole: null,
      onboarded: false,
    });
  },

  // --- Onboarding ---
  displayName: localStorage.getItem('verso_display_name') || null,
  userRole: localStorage.getItem('verso_user_role') || null,
  onboarded: localStorage.getItem('verso_onboarded') === 'true',
  completeOnboarding: (name, role) => {
    localStorage.setItem('verso_display_name', name);
    localStorage.setItem('verso_user_role', role);
    localStorage.setItem('verso_onboarded', 'true');
    set({ displayName: name, userRole: role, onboarded: true });
  },

  // --- Bookmarks (API-backed) ---
  bookmarks: new Map(), // reel_id -> bookmark_id
  bookmarkItems: [],    // full bookmark objects from API
  loadBookmarks: async () => {
    try {
      const items = await getBookmarks();
      const map = new Map();
      items.forEach((b) => {
        if (b.reel_id) map.set(b.reel_id, b.id);
        if (b.flashcard_id) map.set('fc_' + b.flashcard_id, b.id);
      });
      set({ bookmarks: map, bookmarkItems: items });
    } catch {
      // silent fail — bookmarks stay empty
    }
  },
  toggleBookmark: async (reelId) => {
    const { bookmarks } = get();
    if (bookmarks.has(reelId)) {
      const bookmarkId = bookmarks.get(reelId);
      try {
        await apiRemoveBookmark(bookmarkId);
        trackInteraction(reelId, 'unbookmark').catch(() => {});
        const next = new Map(bookmarks);
        next.delete(reelId);
        set((state) => ({
          bookmarks: next,
          bookmarkItems: state.bookmarkItems.filter((b) => b.id !== bookmarkId),
        }));
      } catch { /* silent */ }
    } else {
      try {
        const result = await apiAddBookmark(reelId, null);
        trackInteraction(reelId, 'bookmark').catch(() => {});
        const next = new Map(bookmarks);
        next.set(reelId, result.id);
        set((state) => ({
          bookmarks: next,
          bookmarkItems: [...state.bookmarkItems, { id: result.id, reel_id: reelId }],
        }));
      } catch { /* silent */ }
    }
  },

  // --- Likes (API-backed) ---
  likes: new Map(), // reel_id -> true
  loadLikes: async () => {
    try {
      const data = await getLikedReels();
      const map = new Map();
      data.liked_reel_ids.forEach((id) => map.set(id, true));
      set({ likes: map });
    } catch {
      // silent fail
    }
  },
  toggleLike: async (reelId) => {
    const { likes } = get();
    if (likes.has(reelId)) {
      try {
        await trackInteraction(reelId, 'unlike');
        const next = new Map(likes);
        next.delete(reelId);
        set({ likes: next });
      } catch { /* silent */ }
    } else {
      try {
        await trackInteraction(reelId, 'like');
        const next = new Map(likes);
        next.set(reelId, true);
        set({ likes: next });
      } catch { /* silent */ }
    }
  },

  // --- Reels / Feed ---
  reels: [],
  feedPage: 1,
  hasMore: true,
  setReels: (reels) => set({ reels, feedPage: 1, hasMore: true }),
  appendReels: (newReels) =>
    set((state) => {
      const existingIds = new Set(state.reels.map((r) => r.id))
      const unique = newReels.filter((r) => !existingIds.has(r.id))
      if (unique.length === 0) return state
      return {
        reels: [...state.reels, ...unique],
        feedPage: state.feedPage + 1,
        hasMore: newReels.length > 0,
      }
    }),

  // --- Playback ---
  muted: false,
  setMuted: (val) => set({ muted: val }),
  toggleMuted: () => set((state) => ({ muted: !state.muted })),

  // --- Upload ---
  currentUpload: null, // { id, status, progress }
  setUploadStatus: (upload) => set({ currentUpload: upload }),
  clearUpload: () => set({ currentUpload: null }),

  // --- Background Upload Processing ---
  bgUpload: null, // { id, filename, progress, stage, status }
  setBgUpload: (upload) => set({ bgUpload: upload }),
  updateBgUpload: (updates) =>
    set((state) => ({
      bgUpload: state.bgUpload ? { ...state.bgUpload, ...updates } : null,
    })),
  clearBgUpload: () => set({ bgUpload: null }),

}));

export default useStore;
