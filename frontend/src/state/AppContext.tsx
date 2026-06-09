import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from 'react';
import { apiClient, type ServerState } from '../api/client';
import type {
  ActivityLogEntry,
  RouteKey,
  Site,
  ThemeMode,
  Toast,
  UpdateItem,
  UpdateType,
} from '../types';

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------
interface ConfirmRequest {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
}

interface State {
  sites: Site[];
  updates: UpdateItem[];
  activity: ActivityLogEntry[];
  theme: ThemeMode;
  route: RouteKey;
  updatesTab: 'all' | UpdateType;
  search: string;
  loading: boolean;
  drawerSiteId: string | null;
  drawerEdit: boolean;
  toasts: Toast[];
  confirm: ConfirmRequest | null;
}

type Action =
  | { type: 'SET_THEME'; theme: ThemeMode }
  | { type: 'SET_ROUTE'; route: RouteKey }
  | { type: 'SET_UPDATES_TAB'; tab: 'all' | UpdateType }
  | { type: 'SET_SEARCH'; search: string }
  | { type: 'SET_LOADING'; loading: boolean }
  | { type: 'SET_STATE'; server: ServerState }
  | { type: 'TOGGLE_SITE'; id: string }
  | { type: 'SET_SITES_SELECTED'; ids: string[]; selected: boolean }
  | { type: 'CLEAR_SITE_SELECTION' }
  | { type: 'TOGGLE_UPDATE'; id: string }
  | { type: 'SET_UPDATES_SELECTED'; ids: string[]; selected: boolean }
  | { type: 'PATCH_SITE'; id: string; patch: Partial<Site> }
  | { type: 'PUSH_TOAST'; toast: Toast }
  | { type: 'DISMISS_TOAST'; id: string }
  | { type: 'OPEN_DRAWER'; siteId: string; edit: boolean }
  | { type: 'CLOSE_DRAWER' }
  | { type: 'OPEN_CONFIRM'; request: ConfirmRequest }
  | { type: 'CLOSE_CONFIRM' };

const THEME_KEY = 'wpupdater-theme';

function initialTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'light';
  const stored = window.localStorage.getItem(THEME_KEY) as ThemeMode | null;
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

const initialState: State = {
  sites: [],
  updates: [],
  activity: [],
  theme: initialTheme(),
  route: 'dashboard',
  updatesTab: 'all',
  search: '',
  loading: true,
  drawerSiteId: null,
  drawerEdit: false,
  toasts: [],
  confirm: null,
};

// Merge fresh server data while preserving client-only selection flags.
function mergeServerState(prev: State, server: ServerState): State {
  const selectedSites = new Set(prev.sites.filter((s) => s.selected).map((s) => s.id));
  const selectedUpdates = new Set(prev.updates.filter((u) => u.selected).map((u) => u.id));
  return {
    ...prev,
    sites: server.sites.map((s) => ({ ...s, selected: selectedSites.has(s.id) })),
    updates: server.updates.map((u) => ({ ...u, selected: selectedUpdates.has(u.id) })),
    activity: server.activity,
  };
}

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------
function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_THEME':
      return { ...state, theme: action.theme };
    case 'SET_ROUTE':
      return { ...state, route: action.route };
    case 'SET_UPDATES_TAB':
      return { ...state, updatesTab: action.tab };
    case 'SET_SEARCH':
      return { ...state, search: action.search };
    case 'SET_LOADING':
      return { ...state, loading: action.loading };
    case 'SET_STATE':
      return mergeServerState(state, action.server);
    case 'TOGGLE_SITE':
      return {
        ...state,
        sites: state.sites.map((s) =>
          s.id === action.id ? { ...s, selected: !s.selected } : s,
        ),
      };
    case 'SET_SITES_SELECTED':
      return {
        ...state,
        sites: state.sites.map((s) =>
          action.ids.includes(s.id) ? { ...s, selected: action.selected } : s,
        ),
      };
    case 'CLEAR_SITE_SELECTION':
      return { ...state, sites: state.sites.map((s) => ({ ...s, selected: false })) };
    case 'TOGGLE_UPDATE':
      return {
        ...state,
        updates: state.updates.map((u) =>
          u.id === action.id ? { ...u, selected: !u.selected } : u,
        ),
      };
    case 'SET_UPDATES_SELECTED':
      return {
        ...state,
        updates: state.updates.map((u) =>
          action.ids.includes(u.id) ? { ...u, selected: action.selected } : u,
        ),
      };
    case 'PATCH_SITE':
      return {
        ...state,
        sites: state.sites.map((s) => (s.id === action.id ? { ...s, ...action.patch } : s)),
      };
    case 'PUSH_TOAST':
      return { ...state, toasts: [...state.toasts, action.toast] };
    case 'DISMISS_TOAST':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) };
    case 'OPEN_DRAWER':
      return { ...state, drawerSiteId: action.siteId, drawerEdit: action.edit };
    case 'CLOSE_DRAWER':
      return { ...state, drawerSiteId: null, drawerEdit: false };
    case 'OPEN_CONFIRM':
      return { ...state, confirm: action.request };
    case 'CLOSE_CONFIRM':
      return { ...state, confirm: null };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context value (state + action creators)
// ---------------------------------------------------------------------------
interface AppContextValue {
  state: State;
  setTheme: (t: ThemeMode) => void;
  toggleTheme: () => void;
  setRoute: (r: RouteKey) => void;
  setUpdatesTab: (tab: 'all' | UpdateType) => void;
  setSearch: (q: string) => void;
  toggleSite: (id: string) => void;
  setSitesSelected: (ids: string[], selected: boolean) => void;
  clearSiteSelection: () => void;
  toggleUpdate: (id: string) => void;
  setUpdatesSelected: (ids: string[], selected: boolean) => void;
  openDrawer: (siteId: string, edit?: boolean) => void;
  closeDrawer: () => void;
  pushToast: (t: Omit<Toast, 'id'>) => void;
  dismissToast: (id: string) => void;
  requestConfirm: (r: ConfirmRequest) => void;
  closeConfirm: () => void;
  refresh: () => void;
  addSite: (input: { name: string; url: string; apiKey: string; group: string }) => void;
  removeSite: (siteId: string) => void;
  setAutoUpdate: (siteId: string, enabled: boolean) => void;
  editSite: (
    siteId: string,
    patch: { name?: string; url?: string; apiKey?: string; group?: string },
  ) => void;
  updateItem: (siteId: string, type: UpdateType, slug: string) => void;
  updateSelectedItems: () => void;
  scanSite: (siteId: string) => void;
  scanAll: () => void;
  updateSite: (siteId: string, scope: UpdateType | 'all') => void;
  bulkUpdate: (siteIds: string[], scope: UpdateType | 'all') => void;
  retryActivity: (entryId: string) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

let idCounter = 0;
const uid = (prefix: string) => `${prefix}-${Date.now()}-${idCounter++}`;

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const stateRef = useRef(state);
  stateRef.current = state;

  // Apply theme to <html> and persist.
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', state.theme);
    window.localStorage.setItem(THEME_KEY, state.theme);
  }, [state.theme]);

  const pushToast = useCallback((t: Omit<Toast, 'id'>) => {
    const toast: Toast = { ...t, id: uid('toast') };
    dispatch({ type: 'PUSH_TOAST', toast });
    setTimeout(() => dispatch({ type: 'DISMISS_TOAST', id: toast.id }), 4500);
  }, []);

  const loadState = useCallback(
    async (showLoading = false) => {
      if (showLoading) dispatch({ type: 'SET_LOADING', loading: true });
      try {
        const server = await apiClient.getState();
        dispatch({ type: 'SET_STATE', server });
      } catch (err) {
        pushToast({ title: 'Failed to load data', message: String(err), variant: 'error' });
      } finally {
        if (showLoading) dispatch({ type: 'SET_LOADING', loading: false });
      }
    },
    [pushToast],
  );

  // Initial load.
  useEffect(() => {
    loadState(true);
  }, [loadState]);

  const findSite = (id: string) => stateRef.current.sites.find((s) => s.id === id);

  // -------------------------------------------------------------- scanning
  const scanSite = useCallback(
    async (siteId: string) => {
      const site = findSite(siteId);
      if (!site) return;
      dispatch({ type: 'PATCH_SITE', id: siteId, patch: { status: 'scanning' } });
      try {
        const res = await apiClient.scanSite(siteId);
        dispatch({ type: 'SET_STATE', server: res.state });
      } catch (err) {
        dispatch({ type: 'PATCH_SITE', id: siteId, patch: { status: 'failed' } });
        pushToast({ title: `Scan failed: ${site.name}`, message: String(err), variant: 'error' });
      }
    },
    [pushToast],
  );

  const scanAll = useCallback(async () => {
    pushToast({ title: 'Scanning all sites', message: 'This may take a moment', variant: 'info' });
    stateRef.current.sites.forEach((s) =>
      dispatch({ type: 'PATCH_SITE', id: s.id, patch: { status: 'scanning' } }),
    );
    try {
      const res = await apiClient.scanAll();
      dispatch({ type: 'SET_STATE', server: res.state });
      pushToast({ title: 'Scan complete', variant: 'success' });
    } catch (err) {
      pushToast({ title: 'Scan failed', message: String(err), variant: 'error' });
      loadState();
    }
  }, [pushToast, loadState]);

  // -------------------------------------------------------------- updating
  const updateSite = useCallback(
    async (siteId: string, scope: UpdateType | 'all') => {
      const site = findSite(siteId);
      if (!site) return;
      dispatch({ type: 'PATCH_SITE', id: siteId, patch: { status: 'updating' } });
      try {
        const res = await apiClient.updateSite(siteId, scope);
        dispatch({ type: 'SET_STATE', server: res.state });
        const updated = res.state.sites.find((s) => s.id === siteId);
        pushToast({
          title: `${site.name} updated`,
          message:
            updated && updated.totalUpdates > 0
              ? `${updated.totalUpdates} update(s) remain`
              : 'Up to date',
          variant: 'success',
        });
      } catch (err) {
        dispatch({ type: 'PATCH_SITE', id: siteId, patch: { status: 'failed' } });
        pushToast({ title: `Update failed: ${site.name}`, message: String(err), variant: 'error' });
      }
    },
    [pushToast],
  );

  const bulkUpdate = useCallback(
    async (siteIds: string[], scope: UpdateType | 'all') => {
      pushToast({
        title: 'Bulk update started',
        message: `${siteIds.length} site(s) · ${scope}`,
        variant: 'info',
      });
      siteIds.forEach((id) => dispatch({ type: 'PATCH_SITE', id, patch: { status: 'updating' } }));
      dispatch({ type: 'CLEAR_SITE_SELECTION' });
      try {
        const res = await apiClient.bulkUpdate(siteIds, scope);
        dispatch({ type: 'SET_STATE', server: res.state });
        pushToast({ title: 'Bulk update finished', variant: 'success' });
      } catch (err) {
        pushToast({ title: 'Bulk update failed', message: String(err), variant: 'error' });
        loadState();
      }
    },
    [pushToast, loadState],
  );

  const retryActivity = useCallback(
    (entryId: string) => {
      const entry = stateRef.current.activity.find((a) => a.id === entryId);
      if (!entry || !entry.siteId) return;
      const scope: UpdateType | 'all' =
        entry.action === 'update-core'
          ? 'core'
          : entry.action === 'update-plugins'
            ? 'plugin'
            : entry.action === 'update-themes'
              ? 'theme'
              : 'all';
      updateSite(entry.siteId, scope);
    },
    [updateSite],
  );

  const addSite = useCallback(
    async (input: { name: string; url: string; apiKey: string; group: string }) => {
      try {
        const res = await apiClient.addSite(input);
        dispatch({ type: 'SET_STATE', server: res.state });
        pushToast({ title: 'Site added', message: input.name, variant: 'success' });
      } catch (err) {
        pushToast({ title: 'Could not add site', message: String(err), variant: 'error' });
      }
    },
    [pushToast],
  );

  const removeSite = useCallback(
    async (siteId: string) => {
      const site = findSite(siteId);
      try {
        const res = await apiClient.removeSite(siteId);
        if (stateRef.current.drawerSiteId === siteId) dispatch({ type: 'CLOSE_DRAWER' });
        dispatch({ type: 'SET_STATE', server: res.state });
        pushToast({ title: 'Site removed', message: site?.name, variant: 'success' });
      } catch (err) {
        pushToast({ title: 'Could not remove site', message: String(err), variant: 'error' });
      }
    },
    [pushToast],
  );

  const setAutoUpdate = useCallback(
    async (siteId: string, enabled: boolean) => {
      const site = findSite(siteId);
      if (!site) return;
      try {
        const res = await apiClient.setAutoUpdate(siteId, enabled);
        dispatch({ type: 'SET_STATE', server: res.state });
        pushToast({
          title: enabled ? 'Auto-update enabled' : 'Auto-update disabled',
          message: site.name,
          variant: 'success',
        });
      } catch (err) {
        pushToast({ title: 'Could not change auto-update', message: String(err), variant: 'error' });
      }
    },
    [pushToast],
  );

  const editSite = useCallback(
    async (
      siteId: string,
      patch: { name?: string; url?: string; apiKey?: string; group?: string },
    ) => {
      try {
        const res = await apiClient.editSite(siteId, patch);
        dispatch({ type: 'SET_STATE', server: res.state });
        pushToast({ title: 'Site updated', message: patch.name, variant: 'success' });
      } catch (err) {
        pushToast({ title: 'Could not update site', message: String(err), variant: 'error' });
      }
    },
    [pushToast],
  );

  const updateItem = useCallback(
    async (siteId: string, type: UpdateType, slug: string) => {
      const site = findSite(siteId);
      if (!site) return;
      try {
        const res = await apiClient.updateItem(siteId, type, slug);
        dispatch({ type: 'SET_STATE', server: res.state });
        pushToast({ title: `${site.name} updated`, message: `${type} updated`, variant: 'success' });
      } catch (err) {
        pushToast({ title: `Update failed: ${site.name}`, message: String(err), variant: 'error' });
      }
    },
    [pushToast],
  );

  // Sequentially apply every currently-selected update item, one after another.
  const updateSelectedItems = useCallback(async () => {
    const items = stateRef.current.updates.filter((u) => u.selected);
    if (items.length === 0) {
      pushToast({ title: 'Nothing selected', message: 'Pick one or more updates first', variant: 'info' });
      return;
    }
    pushToast({
      title: 'Updating selected items',
      message: `${items.length} item(s), one at a time`,
      variant: 'info',
    });
    let ok = 0;
    let failed = 0;
    for (const item of items) {
      const site = findSite(item.siteId);
      try {
        const res = await apiClient.updateItem(item.siteId, item.type, item.slug);
        dispatch({ type: 'SET_STATE', server: res.state });
        ok += 1;
      } catch (err) {
        failed += 1;
        pushToast({
          title: `Update failed: ${site?.name ?? item.siteId}`,
          message: `${item.name}: ${String(err)}`,
          variant: 'error',
        });
      }
    }
    pushToast({
      title: 'Selected updates finished',
      message: `${ok} succeeded${failed ? `, ${failed} failed` : ''}`,
      variant: failed ? 'error' : 'success',
    });
  }, [pushToast]);

  const value = useMemo<AppContextValue>(
    () => ({
      state,
      setTheme: (t) => dispatch({ type: 'SET_THEME', theme: t }),
      toggleTheme: () =>
        dispatch({ type: 'SET_THEME', theme: state.theme === 'dark' ? 'light' : 'dark' }),
      setRoute: (r) => dispatch({ type: 'SET_ROUTE', route: r }),
      setUpdatesTab: (tab) => dispatch({ type: 'SET_UPDATES_TAB', tab }),
      setSearch: (q) => dispatch({ type: 'SET_SEARCH', search: q }),
      toggleSite: (id) => dispatch({ type: 'TOGGLE_SITE', id }),
      setSitesSelected: (ids, selected) => dispatch({ type: 'SET_SITES_SELECTED', ids, selected }),
      clearSiteSelection: () => dispatch({ type: 'CLEAR_SITE_SELECTION' }),
      toggleUpdate: (id) => dispatch({ type: 'TOGGLE_UPDATE', id }),
      setUpdatesSelected: (ids, selected) =>
        dispatch({ type: 'SET_UPDATES_SELECTED', ids, selected }),
      openDrawer: (siteId, edit = false) => dispatch({ type: 'OPEN_DRAWER', siteId, edit }),
      closeDrawer: () => dispatch({ type: 'CLOSE_DRAWER' }),
      pushToast,
      dismissToast: (id) => dispatch({ type: 'DISMISS_TOAST', id }),
      requestConfirm: (r) => dispatch({ type: 'OPEN_CONFIRM', request: r }),
      closeConfirm: () => dispatch({ type: 'CLOSE_CONFIRM' }),
      refresh: () => loadState(),
      addSite,
      removeSite,
      setAutoUpdate,
      editSite,
      updateItem,
      updateSelectedItems,
      scanSite,
      scanAll,
      updateSite,
      bulkUpdate,
      retryActivity,
    }),
    [
      state,
      pushToast,
      loadState,
      addSite,
      removeSite,
      setAutoUpdate,
      editSite,
      updateItem,
      updateSelectedItems,
      scanSite,
      scanAll,
      updateSite,
      bulkUpdate,
      retryActivity,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
