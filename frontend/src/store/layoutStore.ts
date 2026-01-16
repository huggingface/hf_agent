import { create } from 'zustand';

interface LayoutStore {
  isLeftSidebarOpen: boolean;
  isRightPanelOpen: boolean;
  rightPanelWidth: number;
  setLeftSidebarOpen: (open: boolean) => void;
  setRightPanelOpen: (open: boolean) => void;
  setRightPanelWidth: (width: number) => void;
  toggleLeftSidebar: () => void;
  toggleRightPanel: () => void;
}

export const useLayoutStore = create<LayoutStore>((set) => ({
  isLeftSidebarOpen: true,
  isRightPanelOpen: false,
  rightPanelWidth: 450,
  setLeftSidebarOpen: (open) => set({ isLeftSidebarOpen: open }),
  setRightPanelOpen: (open) => set({ isRightPanelOpen: open }),
  setRightPanelWidth: (width) => set({ rightPanelWidth: width }),
  toggleLeftSidebar: () => set((state) => ({ isLeftSidebarOpen: !state.isLeftSidebarOpen })),
  toggleRightPanel: () => set((state) => ({ isRightPanelOpen: !state.isRightPanelOpen })),
}));
