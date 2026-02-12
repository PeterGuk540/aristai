'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Upload,
  File,
  FileText,
  Image,
  Film,
  Music,
  Archive,
  Download,
  Trash2,
  Edit2,
  X,
  Check,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Button, Card, CardHeader, CardTitle, CardContent, Input } from '@/components/ui';
import { formatTimestamp } from '@/lib/utils';

interface Material {
  id: number;
  course_id: number;
  session_id: number | null;
  filename: string;
  file_size: number;
  content_type: string;
  title: string | null;
  description: string | null;
  uploaded_by: number | null;
  created_at: string;
  updated_at: string;
  version: number;
  download_url: string | null;
}

interface MaterialsManagerProps {
  courseId: number;
  sessionId?: number;
  isInstructor: boolean;
  userId?: number;
}

const getFileIcon = (contentType: string) => {
  if (contentType.startsWith('image/')) return Image;
  if (contentType.startsWith('video/')) return Film;
  if (contentType.startsWith('audio/')) return Music;
  if (contentType.includes('pdf')) return FileText;
  if (contentType.includes('zip') || contentType.includes('archive')) return Archive;
  return File;
};

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export default function MaterialsManager({
  courseId,
  sessionId,
  isInstructor,
  userId,
}: MaterialsManagerProps) {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchMaterials = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = sessionId
        ? await api.getSessionMaterials(sessionId)
        : await api.getCourseMaterials(courseId);
      setMaterials(response.materials || []);
    } catch (err: any) {
      console.error('Failed to fetch materials:', err);
      setError(err.message || 'Failed to load materials');
    } finally {
      setLoading(false);
    }
  }, [courseId, sessionId]);

  useEffect(() => {
    fetchMaterials();
  }, [fetchMaterials]);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];

    // Check file size (100MB limit)
    const maxSize = 100 * 1024 * 1024;
    if (file.size > maxSize) {
      setError('File too large. Maximum size is 100MB.');
      return;
    }

    try {
      setUploading(true);
      setUploadProgress(10);
      setError(null);

      await api.uploadMaterial(courseId, file, {
        sessionId,
        userId,
      });

      setUploadProgress(100);
      await fetchMaterials();
    } catch (err: any) {
      console.error('Upload failed:', err);
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      setUploadProgress(0);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDownload = (material: Material) => {
    if (material.download_url) {
      window.open(material.download_url, '_blank');
    } else {
      // Fallback to API redirect
      window.open(api.getMaterialDownloadUrl(courseId, material.id), '_blank');
    }
  };

  const handleDelete = async (materialId: number) => {
    if (!confirm('Are you sure you want to delete this material?')) return;

    try {
      await api.deleteMaterial(courseId, materialId);
      await fetchMaterials();
    } catch (err: any) {
      console.error('Delete failed:', err);
      setError(err.message || 'Delete failed');
    }
  };

  const handleEdit = (material: Material) => {
    setEditingId(material.id);
    setEditTitle(material.title || material.filename);
    setEditDescription(material.description || '');
  };

  const handleSaveEdit = async () => {
    if (!editingId) return;

    try {
      await api.updateMaterial(courseId, editingId, {
        title: editTitle,
        description: editDescription,
      });
      setEditingId(null);
      await fetchMaterials();
    } catch (err: any) {
      console.error('Update failed:', err);
      setError(err.message || 'Update failed');
    }
  };

  const handleReplace = async (materialId: number) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      try {
        setUploading(true);
        await api.replaceMaterial(courseId, materialId, file, userId);
        await fetchMaterials();
      } catch (err: any) {
        console.error('Replace failed:', err);
        setError(err.message || 'Replace failed');
      } finally {
        setUploading(false);
      }
    };
    input.click();
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Course Materials
        </CardTitle>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchMaterials}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          {isInstructor && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileSelect}
                disabled={uploading}
                data-voice-id="material-file-input"
              />
              <Button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                data-voice-id="upload-material-button"
              >
                <Upload className="w-4 h-4 mr-2" />
                {uploading ? 'Uploading...' : 'Upload Material'}
              </Button>
            </>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-4 p-3 bg-danger-50 dark:bg-danger-900/20 border border-danger-200 dark:border-danger-900/50 rounded-xl flex items-center gap-2 text-danger-700 dark:text-danger-300">
            <AlertCircle className="w-4 h-4" />
            {error}
            <button onClick={() => setError(null)} className="ml-auto p-1 rounded-md hover:bg-danger-100 dark:hover:bg-danger-900/30">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {uploading && (
          <div className="mb-4">
            <div className="w-full bg-stone-200 dark:bg-stone-800 rounded-full h-2">
              <div
                className="bg-primary-600 h-2 rounded-full transition-all"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">Uploading...</p>
          </div>
        )}

        {loading ? (
          <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">Loading materials...</div>
        ) : materials.length === 0 ? (
          <div className="text-center py-8 text-neutral-500 dark:text-neutral-400">
            <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>No materials uploaded yet.</p>
            {isInstructor && (
              <p className="text-sm mt-1">Click "Upload Material" to add files.</p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {materials.map((material) => {
              const FileIcon = getFileIcon(material.content_type);
              const isEditing = editingId === material.id;

              return (
                <div
                  key={material.id}
                  className="flex items-center gap-3 p-3 bg-stone-50 dark:bg-stone-900/30 rounded-xl border border-stone-200 dark:border-stone-700 hover:bg-stone-100 dark:hover:bg-stone-900/50 transition-colors"
                >
                  <FileIcon className="w-8 h-8 text-primary-500 flex-shrink-0" />

                  <div className="flex-1 min-w-0">
                    {isEditing ? (
                      <div className="space-y-2">
                        <Input
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          placeholder="Title"
                          className="text-sm"
                        />
                        <Input
                          value={editDescription}
                          onChange={(e) => setEditDescription(e.target.value)}
                          placeholder="Description (optional)"
                          className="text-sm"
                        />
                      </div>
                    ) : (
                      <>
                        <p className="font-medium truncate">
                          {material.title || material.filename}
                        </p>
                        {material.description && (
                          <p className="text-sm text-neutral-500 dark:text-neutral-400 truncate">
                            {material.description}
                          </p>
                        )}
                        <p className="text-xs text-neutral-400 dark:text-neutral-500">
                          {formatFileSize(material.file_size)} • {formatTimestamp(material.created_at)}
                          {material.version > 1 && ` • v${material.version}`}
                        </p>
                      </>
                    )}
                  </div>

                  <div className="flex items-center gap-1 flex-shrink-0">
                    {isEditing ? (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={handleSaveEdit}
                          title="Save"
                        >
                          <Check className="w-4 h-4 text-success-600" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingId(null)}
                          title="Cancel"
                        >
                          <X className="w-4 h-4 text-neutral-500" />
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownload(material)}
                          title="Download"
                          data-voice-id={`download-material-${material.id}`}
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                        {isInstructor && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEdit(material)}
                              title="Edit"
                            >
                              <Edit2 className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleReplace(material.id)}
                              title="Replace file"
                            >
                              <RefreshCw className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(material.id)}
                              title="Delete"
                              className="text-danger-500 hover:text-danger-700"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
