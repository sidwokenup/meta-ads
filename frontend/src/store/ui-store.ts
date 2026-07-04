import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));

interface SearchState {
  globalSearch: string;
  setGlobalSearch: (query: string) => void;
}

export const useSearchStore = create<SearchState>((set) => ({
  globalSearch: "",
  setGlobalSearch: (query) => set({ globalSearch: query }),
}));

interface SessionState {
  activeProfileId: string | null;
  activeAccountId: string | null;
  setActiveProfile: (id: string | null) => void;
  setActiveAccount: (id: string | null) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  activeProfileId: "k1dvlyr0", // Placeholder
  activeAccountId: "1559140139101704", // Placeholder
  setActiveProfile: (id) => set({ activeProfileId: id }),
  setActiveAccount: (id) => set({ activeAccountId: id }),
}));
