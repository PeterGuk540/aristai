'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, Download, ExternalLink, Loader2, Plug, RefreshCw } from 'lucide-react';
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
  const [externalCourses, setExternalCourses] = useState<ExternalCourse[]>([]);
  const [externalMaterials, setExternalMaterials] = useState<ExternalMaterial[]>([]);
  const [localCourses, setLocalCourses] = useState<LocalCourse[]>([]);
  const [localSessions, setLocalSessions] = useState<LocalSession[]>([]);
  const [selectedExternalCourse, setSelectedExternalCourse] = useState('');
  const [selectedLocalCourse, setSelectedLocalCourse] = useState('');
  const [selectedLocalSession, setSelectedLocalSession] = useState('');
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const providerState = useMemo(
    () => providers.find((p) => p.name === provider),
    [providers, provider]
  );

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

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await refreshBaseData();
      setLoading(false);
    };
    void run();
  }, [currentUser?.id]);

  useEffect(() => {
    if (!providerState?.enabled || !providerState?.configured) {
      setExternalCourses([]);
      setSelectedExternalCourse('');
      return;
    }
    const run = async () => {
      try {
        const courses = await api.getExternalCourses(provider);
        setExternalCourses(courses);
      } catch (e: any) {
        setError(e?.message || `Failed to load ${provider} courses.`);
      }
    };
    void run();
  }, [provider, providerState?.enabled, providerState?.configured]);

  useEffect(() => {
    setExternalMaterials([]);
    setSelectedMaterialIds([]);
    if (!selectedExternalCourse || !providerState?.enabled || !providerState?.configured) return;
    const run = async () => {
      try {
        const items = await api.getExternalMaterials(provider, selectedExternalCourse);
        setExternalMaterials(items);
      } catch (e: any) {
        setError(e?.message || `Failed to load materials for external course ${selectedExternalCourse}.`);
      }
    };
    void run();
  }, [provider, selectedExternalCourse, providerState?.enabled, providerState?.configured]);

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

  const selectAllMaterials = () => {
    setSelectedMaterialIds(externalMaterials.map((m) => m.external_id));
  };

  const clearMaterials = () => setSelectedMaterialIds([]);

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
        target_session_id: selectedLocalSession ? Number(selectedLocalSession) : undefined,
        uploaded_by: currentUser?.id,
        overwrite_title_prefix: '[Canvas] ',
      });
      setMessage(
        `Import complete. Imported ${result.imported_count}, failed ${result.failed_count}.`
      );
    } catch (e: any) {
      setError(e?.message || 'Import failed.');
    } finally {
      setImporting(false);
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
            Connect external LMS platforms and import course materials into AristAI.
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
        <div className="mb-4 flex items-center gap-2">
          <Plug className="h-4 w-4 text-primary-600" />
          <h2 className="font-semibold text-neutral-900 dark:text-neutral-100">Provider Status</h2>
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
                {p.enabled ? (p.configured ? 'Configured' : 'Not configured') : 'Planned'}
              </p>
            </div>
          ))}
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
              Source External Course
            </label>
            <select
              value={selectedExternalCourse}
              onChange={(e) => setSelectedExternalCourse(e.target.value)}
              data-voice-id="select-external-course"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-900"
              disabled={!providerState?.configured}
            >
              <option value="">{providerState?.configured ? 'Select external course' : 'Configure provider first'}</option>
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
                        {m.filename} · {formatBytes(m.size_bytes)} · {m.content_type}
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
