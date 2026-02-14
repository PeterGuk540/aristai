'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  ExternalLink,
  Link2,
  Loader2,
  Plug,
  RefreshCw,
  RotateCw,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';

type ProviderStatus = { name: string; configured: boolean; enabled: boolean };
type ExternalCourse = { provider: string; external_id: string; title: string; code?: string; term?: string };
type ExternalMaterial = {
  provider: string;
  external_id: string;
  course_external_id: string;
  title: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  updated_at?: string;
  source_url?: string;
};
type LocalCourse = { id: number; title: string };
type LocalSession = { id: number; title: string; status?: string };
type ConnectionCheck = {
  id: number;
  provider: string;
  user_id: number;
  status: string;
  provider_user_id?: string;
  provider_user_name?: string;
  last_checked_at?: string;
};
type ProviderConnection = {
  id: number;
  provider: string;
  label: string;
  api_base_url: string;
  token_masked: string;
  is_active: boolean;
  is_default: boolean;
  last_tested_at?: string;
  last_test_status?: string;
  last_test_error?: string;
};
type Mapping = {
  id: number;
  provider: string;
  external_course_id: string;
  external_course_name?: string;
  source_connection_id?: number;
  target_course_id: number;
  created_by?: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
};
type SyncJob = {
  id: number;
  provider: string;
  source_course_external_id: string;
  source_connection_id?: number;
  target_course_id: number;
  target_session_id?: number;
  status: string;
  requested_count: number;
  imported_count: number;
  skipped_count: number;
  failed_count: number;
  created_at?: string;
};

const formatBytes = (bytes: number) => {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let idx = 0;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[idx]}`;
};

export default function IntegrationsPage() {
  const { isInstructor, isAdmin, currentUser } = useUser();
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [provider, setProvider] = useState('canvas');
  const [connectionCheck, setConnectionCheck] = useState<ConnectionCheck | null>(null);
  const [checkingConnection, setCheckingConnection] = useState(false);
  const [providerConnections, setProviderConnections] = useState<ProviderConnection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState('');
  const [newConnLabel, setNewConnLabel] = useState('');
  const [newConnUrl, setNewConnUrl] = useState('');
  const [newConnToken, setNewConnToken] = useState('');
  const [savingProviderConnection, setSavingProviderConnection] = useState(false);
  const [externalCourses, setExternalCourses] = useState<ExternalCourse[]>([]);
  const [externalMaterials, setExternalMaterials] = useState<ExternalMaterial[]>([]);
  const [localCourses, setLocalCourses] = useState<LocalCourse[]>([]);
  const [localSessions, setLocalSessions] = useState<LocalSession[]>([]);
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [selectedMappingId, setSelectedMappingId] = useState('');
  const [selectedExternalCourse, setSelectedExternalCourse] = useState('');
  const [selectedLocalCourse, setSelectedLocalCourse] = useState('');
  const [selectedLocalSession, setSelectedLocalSession] = useState('');
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);
  const [importing, setImporting] = useState(false);
  const [savingMapping, setSavingMapping] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const providerState = useMemo(
    () => providers.find((p) => p.name === provider),
    [providers, provider]
  );
  const activeConnectionId = selectedConnectionId ? Number(selectedConnectionId) : undefined;
  const canReadExternal = Boolean(activeConnectionId || providerState?.configured);

  const localCourseTitleById = useMemo(() => {
    const out: Record<number, string> = {};
    for (const c of localCourses) out[c.id] = c.title;
    return out;
  }, [localCourses]);

  const refreshBaseData = async () => {
    setError('');
    setMessage('');
    try {
      const [providerData, myCourses] = await Promise.all([
        api.getIntegrationProviders(),
        api.getCourses(currentUser?.id),
      ]);
      setProviders(providerData);
      setLocalCourses((myCourses || []).map((c: any) => ({ id: c.id, title: c.title })));
    } catch (e: any) {
      setError(e?.message || 'Failed to load integration data.');
    }
  };

  const refreshProviderData = async () => {
    if (!providerState?.enabled) {
      setProviderConnections([]);
      setExternalCourses([]);
      setMappings([]);
      setJobs([]);
      return;
    }
    try {
      const connections = await api.listProviderConnections(provider);
      setProviderConnections(connections);

      let effectiveConnectionId = activeConnectionId;
      if (!effectiveConnectionId && connections.length > 0) {
        const preferred = connections.find((c) => c.is_default) || connections[0];
        effectiveConnectionId = preferred.id;
        setSelectedConnectionId(String(preferred.id));
      }

      const [courses, mappingRows, jobRows] = await Promise.all([
        (effectiveConnectionId || providerState?.configured)
          ? api.getExternalCourses(provider, effectiveConnectionId)
          : Promise.resolve([]),
        api.listIntegrationMappings(provider, undefined, effectiveConnectionId),
        api.listIntegrationSyncJobs(provider, undefined, 10, effectiveConnectionId),
      ]);

      setExternalCourses(courses);
      setMappings(mappingRows);
      setJobs(jobRows);
    } catch (e: any) {
      setError(e?.message || `Failed to load ${provider} integration data.`);
    }
  };

  const handleConnectionCheck = async () => {
    if (!currentUser?.id || !providerState?.enabled || !canReadExternal) return;
    setCheckingConnection(true);
    setError('');
    try {
      const row = await api.checkIntegrationConnection(provider, currentUser.id, activeConnectionId);
      setConnectionCheck(row);
    } catch (e: any) {
      setConnectionCheck(null);
      setError(e?.message || 'Connection check failed.');
    } finally {
      setCheckingConnection(false);
    }
  };

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await refreshBaseData();
      setLoading(false);
    };
    void run();
  }, [currentUser?.id]);

  useEffect(() => {
    const run = async () => {
      await refreshProviderData();
      await handleConnectionCheck();
    };
    void run();
  }, [provider, providerState?.enabled, providerState?.configured, currentUser?.id, selectedConnectionId]);

  useEffect(() => {
    if (!selectedMappingId) return;
    const selected = mappings.find((m) => String(m.id) === selectedMappingId);
    if (!selected) return;
    setSelectedLocalCourse(String(selected.target_course_id));
    setSelectedExternalCourse(selected.external_course_id);
    if (selected.source_connection_id) {
      setSelectedConnectionId(String(selected.source_connection_id));
    }
  }, [selectedMappingId, mappings]);

  useEffect(() => {
    setExternalMaterials([]);
    setSelectedMaterialIds([]);
    if (!selectedExternalCourse || !providerState?.enabled || !canReadExternal) return;
    const run = async () => {
      try {
        const items = await api.getExternalMaterials(provider, selectedExternalCourse, activeConnectionId);
        setExternalMaterials(items);
      } catch (e: any) {
        setError(e?.message || `Failed to load materials for external course ${selectedExternalCourse}.`);
      }
    };
    void run();
  }, [provider, selectedExternalCourse, providerState?.enabled, canReadExternal, activeConnectionId]);

  useEffect(() => {
    setLocalSessions([]);
    setSelectedLocalSession('');
    if (!selectedLocalCourse) return;
    const run = async () => {
      try {
        const sessions = await api.getCourseSessions(Number(selectedLocalCourse));
        setLocalSessions((sessions || []).map((s: any) => ({ id: s.id, title: s.title, status: s.status })));
      } catch {
        setLocalSessions([]);
      }
    };
    void run();
  }, [selectedLocalCourse]);

  const toggleMaterial = (id: string) => {
    setSelectedMaterialIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectAllMaterials = () => setSelectedMaterialIds(externalMaterials.map((m) => m.external_id));
  const clearMaterials = () => setSelectedMaterialIds([]);

  const handleAddProviderConnection = async () => {
    setError('');
    setMessage('');
    if (!newConnLabel.trim() || !newConnUrl.trim() || !newConnToken.trim()) {
      setError('Label, API URL, and API token are required.');
      return;
    }
    setSavingProviderConnection(true);
    try {
      const created = await api.createProviderConnection(provider, {
        label: newConnLabel.trim(),
        api_base_url: newConnUrl.trim(),
        api_token: newConnToken.trim(),
        is_default: providerConnections.length === 0,
        created_by: currentUser?.id,
      });
      setSelectedConnectionId(String(created.id));
      setNewConnLabel('');
      setNewConnUrl('');
      setNewConnToken('');
      setMessage(`Connection "${created.label}" added.`);
      await refreshProviderData();
    } catch (e: any) {
      setError(e?.message || 'Could not add provider connection.');
    } finally {
      setSavingProviderConnection(false);
    }
  };

  const handleTestActiveConnection = async () => {
    if (!activeConnectionId) {
      setError('Select a provider connection first.');
      return;
    }
    try {
      await api.testProviderConnection(provider, activeConnectionId);
      setMessage('Connection test complete.');
      await refreshProviderData();
    } catch (e: any) {
      setError(e?.message || 'Connection test failed.');
    }
  };

  const handleActivateConnection = async () => {
    if (!activeConnectionId) {
      setError('Select a provider connection first.');
      return;
    }
    try {
      await api.activateProviderConnection(provider, activeConnectionId);
      setMessage('Connection is now default.');
      await refreshProviderData();
    } catch (e: any) {
      setError(e?.message || 'Could not activate connection.');
    }
  };

  const handleSaveMapping = async () => {
    setError('');
    setMessage('');
    if (!selectedLocalCourse || !selectedExternalCourse) {
      setError('Choose both source external course and target AristAI course before saving mapping.');
      return;
    }
    setSavingMapping(true);
    try {
      const source = externalCourses.find((c) => c.external_id === selectedExternalCourse);
      const mapped = await api.createIntegrationMapping(provider, {
        target_course_id: Number(selectedLocalCourse),
        source_course_external_id: selectedExternalCourse,
        source_course_name: source?.title,
        source_connection_id: activeConnectionId,
        created_by: currentUser?.id,
      });
      setSelectedMappingId(String(mapped.id));
      await refreshProviderData();
      setMessage('Course mapping saved.');
    } catch (e: any) {
      setError(e?.message || 'Could not save mapping.');
    } finally {
      setSavingMapping(false);
    }
  };

  const handleImport = async () => {
    setError('');
    setMessage('');
    if (!selectedLocalCourse) {
      setError('Select a target AristAI course first.');
      return;
    }
    if (!selectedExternalCourse) {
      setError('Select a source external course first.');
      return;
    }
    if (!selectedMaterialIds.length) {
      setError('Select at least one material to import.');
      return;
    }

    setImporting(true);
    try {
      const result = await api.importExternalMaterials(provider, {
        target_course_id: Number(selectedLocalCourse),
        source_course_external_id: selectedExternalCourse,
        material_external_ids: selectedMaterialIds,
        source_connection_id: activeConnectionId,
        target_session_id: selectedLocalSession ? Number(selectedLocalSession) : undefined,
        uploaded_by: currentUser?.id,
        overwrite_title_prefix: '[Canvas] ',
      });
      setMessage(
        `Import complete. Imported ${result.imported_count}, skipped ${result.skipped_count ?? 0}, failed ${result.failed_count}.`
      );
      await refreshProviderData();
    } catch (e: any) {
      setError(e?.message || 'Import failed.');
    } finally {
      setImporting(false);
    }
  };

  const handleSyncAll = async () => {
    setError('');
    setMessage('');
    if (!selectedLocalCourse) {
      setError('Select a target AristAI course first.');
      return;
    }
    if (!selectedExternalCourse) {
      setError('Select a source external course first.');
      return;
    }
    setSyncing(true);
    try {
      const result = await api.syncExternalMaterials(provider, {
        target_course_id: Number(selectedLocalCourse),
        source_course_external_id: selectedExternalCourse,
        source_connection_id: activeConnectionId,
        target_session_id: selectedLocalSession ? Number(selectedLocalSession) : undefined,
        uploaded_by: currentUser?.id,
        overwrite_title_prefix: '[Canvas] ',
        mapping_id: selectedMappingId ? Number(selectedMappingId) : undefined,
      });
      setMessage(
        `Sync job #${result.job_id} complete. Imported ${result.imported_count}, skipped ${result.skipped_count}, failed ${result.failed_count}.`
      );
      await refreshProviderData();
    } catch (e: any) {
      setError(e?.message || 'Sync failed.');
    } finally {
      setSyncing(false);
    }
  };

  if (!isInstructor && !isAdmin) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
        <p className="font-semibold">Instructor access required</p>
        <p className="mt-1 text-sm">Only instructors/admins can use LMS integrations.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-neutral-600 dark:text-neutral-300">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading integrations...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100">LMS Integrations</h1>
          <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
            Connect each partner LMS tenant separately, then map and sync materials into AristAI.
          </p>
        </div>
        <button
          onClick={() => void refreshBaseData()}
          data-voice-id="refresh-integrations"
          className="inline-flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-900/30"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-[#1a150c]">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Plug className="h-4 w-4 text-primary-600" />
            <h2 className="font-semibold text-neutral-900 dark:text-neutral-100">Provider Status</h2>
          </div>
          <button
            onClick={() => void handleConnectionCheck()}
            disabled={checkingConnection || !canReadExternal}
            data-voice-id="check-integration-connection"
            className="inline-flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-1.5 text-xs hover:bg-stone-100 disabled:opacity-60 dark:border-stone-700 dark:hover:bg-stone-900/30"
          >
            {checkingConnection ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link2 className="h-3.5 w-3.5" />}
            Check connection
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {providers.map((p) => (
            <div
              key={p.name}
              className="rounded-xl border border-stone-200 p-3 dark:border-stone-700"
              data-voice-id={`provider-${p.name}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium capitalize">{p.name}</span>
                {p.enabled ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-amber-600" />
                )}
              </div>
              <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                {p.enabled ? (p.configured ? 'Global credentials available' : 'Use saved connection') : 'Planned'}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-3 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-xs dark:border-stone-700 dark:bg-stone-900/30">
          {connectionCheck ? (
            <span className="text-emerald-700 dark:text-emerald-300">
              Connected as {connectionCheck.provider_user_name || `user ${connectionCheck.user_id}`}.
            </span>
          ) : (
            <span className="text-neutral-600 dark:text-neutral-300">No verified connection yet.</span>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-[#1a150c]">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-500">
              Source Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              data-voice-id="select-integration-provider"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            >
              {providers
                .filter((p) => p.enabled)
                .map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name.toUpperCase()}
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-500">
              Provider Connection
            </label>
            <select
              value={selectedConnectionId}
              onChange={(e) => setSelectedConnectionId(e.target.value)}
              data-voice-id="select-provider-connection"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            >
              <option value="">Use global env credentials</option>
              {providerConnections.map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.label} ({c.token_masked}) {c.is_default ? '[default]' : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2 grid gap-2 md:grid-cols-3">
            <input
              value={newConnLabel}
              onChange={(e) => setNewConnLabel(e.target.value)}
              data-voice-id="new-provider-connection-label"
              placeholder="Connection label (e.g., UPP Canvas)"
              className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            />
            <input
              value={newConnUrl}
              onChange={(e) => setNewConnUrl(e.target.value)}
              data-voice-id="new-provider-connection-url"
              placeholder="API base URL (e.g., https://.../api/v1)"
              className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            />
            <input
              value={newConnToken}
              onChange={(e) => setNewConnToken(e.target.value)}
              data-voice-id="new-provider-connection-token"
              placeholder="API token"
              type="password"
              className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            />
          </div>

          <div className="flex items-end gap-2">
            <button
              onClick={handleAddProviderConnection}
              disabled={savingProviderConnection}
              data-voice-id="add-provider-connection"
              className="inline-flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm hover:bg-stone-100 disabled:opacity-60 dark:border-stone-700 dark:hover:bg-stone-900/30"
            >
              {savingProviderConnection ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}
              Add connection
            </button>
            <button
              onClick={handleTestActiveConnection}
              data-voice-id="test-provider-connection"
              className="inline-flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm hover:bg-stone-100 disabled:opacity-60 dark:border-stone-700 dark:hover:bg-stone-900/30"
            >
              Test selected
            </button>
            <button
              onClick={handleActivateConnection}
              data-voice-id="activate-provider-connection"
              className="inline-flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm hover:bg-stone-100 disabled:opacity-60 dark:border-stone-700 dark:hover:bg-stone-900/30"
            >
              Set default
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-[#1a150c]">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-500">
              Saved Mapping
            </label>
            <select
              value={selectedMappingId}
              onChange={(e) => setSelectedMappingId(e.target.value)}
              data-voice-id="select-integration-mapping"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            >
              <option value="">No mapping selected</option>
              {mappings.map((m) => (
                <option key={m.id} value={String(m.id)}>
                  {m.external_course_name || m.external_course_id} {'->'} {localCourseTitleById[m.target_course_id] || m.target_course_id}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-500">
              Source External Course
            </label>
            <select
              value={selectedExternalCourse}
              onChange={(e) => setSelectedExternalCourse(e.target.value)}
              data-voice-id="select-external-course"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
              disabled={!canReadExternal}
            >
              <option value="">{canReadExternal ? 'Select external course' : 'Select or add a connection first'}</option>
              {externalCourses.map((c) => (
                <option key={c.external_id} value={c.external_id}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-500">
              Target AristAI Course
            </label>
            <select
              value={selectedLocalCourse}
              onChange={(e) => setSelectedLocalCourse(e.target.value)}
              data-voice-id="select-target-course"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
            >
              <option value="">Select target course</option>
              {localCourses.map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.08em] text-neutral-500">
              Target Session (Optional)
            </label>
            <select
              value={selectedLocalSession}
              onChange={(e) => setSelectedLocalSession(e.target.value)}
              data-voice-id="select-target-session"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
              disabled={!selectedLocalCourse}
            >
              <option value="">Course-level material (no session)</option>
              {localSessions.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.title}
                  {s.status ? ` (${s.status})` : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end gap-2">
            <button
              onClick={handleSaveMapping}
              disabled={savingMapping}
              data-voice-id="save-course-mapping"
              className="inline-flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm hover:bg-stone-100 disabled:opacity-60 dark:border-stone-700 dark:hover:bg-stone-900/30"
            >
              {savingMapping ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
              Save mapping
            </button>
            <button
              onClick={handleSyncAll}
              disabled={syncing}
              data-voice-id="sync-all-materials"
              className="inline-flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm hover:bg-stone-100 disabled:opacity-60 dark:border-stone-700 dark:hover:bg-stone-900/30"
            >
              {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCw className="h-4 w-4" />}
              Sync all
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-[#1a150c]">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold text-neutral-900 dark:text-neutral-100">External Materials</h2>
          <div className="flex gap-2">
            <button
              onClick={selectAllMaterials}
              data-voice-id="select-all-external-materials"
              className="rounded-lg border border-stone-300 px-2 py-1 text-xs hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-900/30"
              disabled={!externalMaterials.length}
            >
              Select all
            </button>
            <button
              onClick={clearMaterials}
              data-voice-id="clear-external-materials"
              className="rounded-lg border border-stone-300 px-2 py-1 text-xs hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-900/30"
              disabled={!selectedMaterialIds.length}
            >
              Clear
            </button>
          </div>
        </div>

        {!externalMaterials.length ? (
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            Select an external course to load materials.
          </p>
        ) : (
          <div className="space-y-2">
            {externalMaterials.map((m) => {
              const checked = selectedMaterialIds.includes(m.external_id);
              return (
                <label
                  key={m.external_id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-stone-200 px-3 py-2 text-sm dark:border-stone-700"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMaterial(m.external_id)}
                      data-voice-id={`external-material-${m.external_id}`}
                    />
                    <div className="min-w-0">
                      <p className="truncate font-medium">{m.title}</p>
                      <p className="truncate text-xs text-neutral-500 dark:text-neutral-400">
                        {m.filename} | {formatBytes(m.size_bytes)} | {m.content_type}
                      </p>
                    </div>
                  </div>
                  {m.source_url && (
                    <a
                      href={m.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-primary-600 hover:underline"
                    >
                      <ExternalLink className="h-3 w-3" />
                      Source
                    </a>
                  )}
                </label>
              );
            })}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-[#1a150c]">
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleImport}
            disabled={importing}
            data-voice-id="import-external-materials"
            className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-60"
          >
            {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Import selected materials
          </button>
          {!!selectedMaterialIds.length && (
            <span className="text-sm text-neutral-600 dark:text-neutral-300">
              {selectedMaterialIds.length} selected
            </span>
          )}
        </div>

        <div className="mt-5 border-t border-stone-200 pt-4 dark:border-stone-700">
          <h3 className="mb-2 text-sm font-semibold text-neutral-900 dark:text-neutral-100">Recent Sync Jobs</h3>
          {!jobs.length ? (
            <p className="text-xs text-neutral-500 dark:text-neutral-400">No sync jobs recorded yet.</p>
          ) : (
            <div className="space-y-2">
              {jobs.map((j) => (
                <div
                  key={j.id}
                  className="rounded-lg border border-stone-200 px-3 py-2 text-xs dark:border-stone-700"
                  data-voice-id={`sync-job-${j.id}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">
                      Job #{j.id} ({j.status})
                    </span>
                    <span className="text-neutral-500 dark:text-neutral-400">
                      {j.created_at ? new Date(j.created_at).toLocaleString() : ''}
                    </span>
                  </div>
                  <p className="mt-1 text-neutral-600 dark:text-neutral-300">
                    Requested {j.requested_count}, imported {j.imported_count}, skipped {j.skipped_count}, failed {j.failed_count}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {message && (
          <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300">
            {message}
          </p>
        )}
        {error && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
            {error}
          </p>
        )}
      </section>
    </div>
  );
}
