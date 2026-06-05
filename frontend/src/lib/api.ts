import type {
  Actor,
  ActorListResponse,
  BatchUploadResponse,
  HealthStatus,
  SystemStatus,
  ToolJob,
  ToolJobsResponse,
  UploadResponse,
  Video,
} from '../types'

declare global {
  interface Window {
    __FACE_SERVICE_CONFIG__?: {
      apiBaseUrl?: string
    }
  }
}

function resolveApiBase(): string {
  const params = new URLSearchParams(window.location.search)
  const configured =
    params.get('apiBaseUrl') ||
    window.__FACE_SERVICE_CONFIG__?.apiBaseUrl ||
    import.meta.env.VITE_API_BASE_URL ||
    '/api'
  const normalized = configured.replace(/\/+$/, '')
  return normalized.endsWith('/api') ? normalized : `${normalized}/api`
}

const API_BASE = resolveApiBase()

export function getApiBaseUrl(): string {
  return API_BASE
}

export function resolveMediaUrl(url?: string | null): string | undefined {
  if (!url) return undefined
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  
  let normalizedUrl = url
  if (normalizedUrl.startsWith('api/')) {
    normalizedUrl = '/' + normalizedUrl
  }
  
  if (normalizedUrl.startsWith('/api/')) {
    const base = getApiBaseUrl()
    return base.slice(0, -4) + normalizedUrl
  }
  
  return url
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') {
        return new Error(body.detail)
      }
    } catch {
      // Fall back to text below.
    }
  }

  const text = await response.text()
  return new Error(text || fallback)
}

export async function uploadImage(file: File, signal?: AbortSignal): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    throw await responseError(response, 'Upload failed')
  }

  return response.json()
}

export async function uploadBatch(files: File[]): Promise<BatchUploadResponse> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }

  const response = await fetch(`${API_BASE}/upload/batch`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw await responseError(response, 'Batch upload failed')
  }

  return response.json()
}

export async function getActors(
  page: number = 1,
  pageSize: number = 20,
  search?: string,
  filters?: {
    breastType?: 'FAKE' | 'NATURAL' | 'NA'
    minScenes?: number
    hasPhoto?: boolean
  },
): Promise<ActorListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  if (search) {
    params.set('search', search)
  }
  if (filters?.breastType) {
    params.set('breast_type', filters.breastType)
  }
  if (filters?.minScenes !== undefined) {
    params.set('min_scenes', String(filters.minScenes))
  }
  if (filters?.hasPhoto !== undefined) {
    params.set('has_photo', String(filters.hasPhoto))
  }

  const response = await fetch(`${API_BASE}/actors?${params}`, {
    method: 'GET',
  })

  if (!response.ok) {
    throw await responseError(response, 'Failed to fetch actors')
  }

  return response.json()
}

export async function getActor(id: number): Promise<Actor> {
  const response = await fetch(`${API_BASE}/actors/${id}`)

  if (!response.ok) {
    throw await responseError(response, 'Failed to fetch actor')
  }

  return response.json()
}

export async function createActor(data: {
  name: string
  birth_year?: number
  gender?: string
  bio?: string
  filmography?: string
  tags?: string
}): Promise<Actor> {
  const formData = new FormData()
  formData.append('name', data.name)
  if (data.birth_year) formData.append('birth_year', String(data.birth_year))
  if (data.gender) formData.append('gender', data.gender)
  if (data.bio) formData.append('bio', data.bio)
  if (data.filmography) formData.append('filmography', data.filmography)
  if (data.tags) formData.append('tags', data.tags)

  const response = await fetch(`${API_BASE}/actors`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw await responseError(response, 'Failed to create actor')
  }

  return response.json()
}

export async function deleteActor(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/actors/${id}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw await responseError(response, 'Failed to delete actor')
  }
}

export async function addActorImage(
  actorId: number,
  file: File,
): Promise<{ message: string; actor_id: number }> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/actors/${actorId}/images`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw await responseError(response, 'Failed to add actor image')
  }

  return response.json()
}

export async function getHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_BASE}/health`)

  if (!response.ok) {
    throw await responseError(response, 'Failed to get health status')
  }

  return response.json()
}

export async function getSystemStatus(): Promise<SystemStatus> {
  const response = await fetch(`${API_BASE}/system/status`)
  if (!response.ok) {
    throw await responseError(response, 'Failed to get system status')
  }
  return response.json()
}

export async function searchStashdb(
  q: string,
  page: number = 1,
  pageSize: number = 20,
): Promise<{
  count: number
  performers: Array<{
    id: string
    name: string
    disambiguation: string | null
    gender: string
    birth_date: string | null
    scene_count: number
    breast_type: string | null
    image_url: string | null
  }>
  page: number
  page_size: number
}> {
  const params = new URLSearchParams({
    q,
    page: String(page),
    page_size: String(pageSize),
  })
  const response = await fetch(`${API_BASE}/stashdb/search?${params}`)
  if (!response.ok) {
    throw await responseError(response, 'Failed to search StashDB')
  }
  return response.json()
}

export async function importStashdbPerformer(
  performerId: string,
  options?: {
    imageCount?: number
    imageOrder?: 'largest' | 'end' | 'start'
    checkFace?: boolean
    overwriteMetadata?: boolean
  }
): Promise<{
  status: 'imported' | 'exists'
  actor: Actor
  images_downloaded: number
  faces_indexed: number
}> {
  const response = await fetch(`${API_BASE}/stashdb/import`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      performer_id: performerId,
      image_count: options?.imageCount ?? 3,
      image_order: options?.imageOrder ?? 'largest',
      check_face: options?.checkFace ?? true,
      overwrite_metadata: options?.overwriteMetadata ?? false,
    }),
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to import performer')
  }
  return response.json()
}

export async function assignFace(
  imageId: string,
  data: {
    actorId?: number
    faceBbox: number[]
    newActorName?: string
    newActorGender?: string
    newActorBirthYear?: number
  }
): Promise<{
  status: 'assigned'
  actor_id: number
  actor_name: string
  faces_indexed: number
}> {
  const response = await fetch(`${API_BASE}/uploads/${imageId}/assign`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      actor_id: data.actorId,
      face_bbox: data.faceBbox,
      new_actor_name: data.newActorName,
      new_actor_gender: data.newActorGender,
      new_actor_birth_year: data.newActorBirthYear,
    }),
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to assign face')
  }
  return response.json()
}

export async function getVideos(filters?: {
  search?: string
  status?: string
  actorId?: number
}): Promise<Video[]> {
  const params = new URLSearchParams()
  if (filters?.search) params.set('search', filters.search)
  if (filters?.status) params.set('status', filters.status)
  if (filters?.actorId !== undefined) params.set('actor_id', String(filters.actorId))

  const response = await fetch(`${API_BASE}/videos?${params}`)
  if (!response.ok) {
    throw await responseError(response, 'Failed to fetch videos')
  }
  return response.json()
}

export async function getVideo(id: number): Promise<Video> {
  const response = await fetch(`${API_BASE}/videos/${id}`)
  if (!response.ok) {
    throw await responseError(response, 'Failed to fetch video details')
  }
  return response.json()
}

export async function scanVideos(): Promise<{
  scanned: number
  added: number
  directory: string
}> {
  const response = await fetch(`${API_BASE}/videos/scan`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to scan videos directory')
  }
  return response.json()
}

export async function processVideo(id: number): Promise<{ status: string; video_id: number }> {
  const response = await fetch(`${API_BASE}/videos/${id}/process`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to process video')
  }
  return response.json()
}

export async function deleteVideo(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/videos/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to delete video')
  }
}

export async function processUnprocessedVideos(): Promise<{ status: string; count: number }> {
  const response = await fetch(`${API_BASE}/videos/process-unprocessed`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to start batch processing')
  }
  return response.json()
}

export async function renameVideo(id: number, newFilename: string): Promise<{ status: string; new_filepath: string; new_filename: string }> {
  const response = await fetch(`${API_BASE}/videos/${id}/rename`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ new_filename: newFilename }),
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to rename video')
  }
  return response.json()
}

export async function matchStashdbScene(id: number): Promise<{
  status: string
  scene_id: string
  title: string
  studio: string | null
  cover_downloaded: boolean
  performers: string[]
}> {
  const response = await fetch(`${API_BASE}/videos/${id}/match-stashdb`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to match StashDB scene')
  }
  return response.json()
}

export interface StashdbSearchResult {
  candidates: Array<{
    scene_id: string
    title: string
    studio: string | null
    date: string | null
    cover_url: string | null
    performers: string[]
    score: number
  }>
  search_info: {
    filename: string
    detected_actors: string[]
    queries_used: Array<{ query: string; results: number; new: number }>
    total_unique_results: number
  }
}

export async function searchStashdbCandidates(id: number): Promise<StashdbSearchResult> {
  const response = await fetch(`${API_BASE}/videos/${id}/search-stashdb`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to search StashDB candidates')
  }
  return response.json()
}

export async function linkStashdb(
  id: number,
  data: {
    scene_id: string
    title: string
    studio: string | null
    cover_url: string | null
    performers?: string[]
  }
): Promise<{ status: string; scene_id: string; cover_downloaded: boolean }> {
  const response = await fetch(`${API_BASE}/videos/${id}/link-stashdb`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to link StashDB scene')
  }
  return response.json()
}

export async function linkStashdbByUrl(
  id: number,
  sceneUrl: string,
): Promise<{
  status: string
  scene_id: string
  title: string
  studio: string | null
  date: string | null
  cover_url: string | null
  cover_downloaded: boolean
  performers: string[]
}> {
  const response = await fetch(`${API_BASE}/videos/${id}/link-stashdb-url`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ scene_url: sceneUrl }),
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to link StashDB scene URL')
  }
  return response.json()
}

export async function addActorToVideo(videoId: number, actorId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/actors/${actorId}`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to add actor to video')
  }
}

export async function removeActorFromVideo(videoId: number, actorId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/actors/${actorId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to remove actor from video')
  }
}

export async function rebuildIndex(refreshCache: boolean = false): Promise<{
  status: string
  rebuild: {
    running: boolean
    started_at: number | null
    finished_at: number | null
    exit_code: number | null
    message: string | null
  }
}> {
  const response = await fetch(`${API_BASE}/index/rebuild?refresh_cache=${refreshCache}`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to rebuild index')
  }
  return response.json()
}

export async function getIndexStatus(): Promise<{
  actors_count: number
  actor_images_count: number
  cached_embedding_files: number
  faiss_index: { exists: boolean; size_bytes: number; updated_at: number | null }
  faiss_id_map: { exists: boolean; size_bytes: number; updated_at: number | null }
  rebuild: {
    running: boolean
    started_at: number | null
    finished_at: number | null
    exit_code: number | null
    message: string | null
  }
}> {
  const response = await fetch(`${API_BASE}/index/status`)
  if (!response.ok) {
    throw await responseError(response, 'Failed to fetch index status')
  }
  return response.json()
}

export async function getToolJobs(): Promise<ToolJobsResponse> {
  const response = await fetch(`${API_BASE}/tools/jobs`)
  if (!response.ok) {
    throw await responseError(response, 'Failed to fetch maintenance jobs')
  }
  return response.json()
}

export async function getToolJob(id: string): Promise<ToolJob> {
  const response = await fetch(`${API_BASE}/tools/jobs/${id}`)
  if (!response.ok) {
    throw await responseError(response, 'Failed to fetch maintenance job')
  }
  return response.json()
}

export async function getToolJobLogs(id: string, tailBytes: number = 20000): Promise<string> {
  const response = await fetch(`${API_BASE}/tools/jobs/${id}/logs?tail_bytes=${tailBytes}`)
  if (!response.ok) {
    throw await responseError(response, 'Failed to fetch maintenance job logs')
  }
  return response.text()
}

export async function startToolJob(
  jobType: string,
  options?: {
    apply?: boolean
    args?: string[]
    env?: Record<string, string>
  },
): Promise<{ status: string; job: ToolJob }> {
  const response = await fetch(`${API_BASE}/tools/jobs/${jobType}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      apply: options?.apply ?? false,
      args: options?.args ?? [],
      env: options?.env ?? {},
    }),
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to start maintenance job')
  }
  return response.json()
}

export async function cancelToolJob(id: string): Promise<{ status: string; job: ToolJob }> {
  const response = await fetch(`${API_BASE}/tools/jobs/${id}/cancel`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw await responseError(response, 'Failed to cancel maintenance job')
  }
  return response.json()
}
export interface DesktopConfig {
  schemaVersion: number;
  runtime: {
    baseDir: string;
    actorsDir: string;
    modelsDir: string;
    faissIndexDir: string;
    videosDir: string;
    jobsDir: string;
    logsDir: string;
  };
  backend: {
    host: string;
    port: number;
    desktopMode: boolean;
    corsOrigins: string[];
  };
  ai: {
    faceExecutionProviders: string[];
    faceModelName: string;
  };
}

export interface ValidationResponse {
  status: 'ok' | 'warning' | 'error';
  errors: string[];
  warnings: string[];
  restartRequired: boolean;
}

export async function getDesktopConfig(): Promise<DesktopConfig> {
  const res = await fetch(`${API_BASE}/desktop/config`);
  if (!res.ok) throw new Error('Failed to fetch desktop config');
  return res.json();
}

export async function validateDesktopConfig(config: DesktopConfig): Promise<ValidationResponse> {
  const res = await fetch(`${API_BASE}/desktop/config/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to validate config');
  return res.json();
}

export async function saveDesktopConfig(config: DesktopConfig): Promise<ValidationResponse> {
  const res = await fetch(`${API_BASE}/desktop/config/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => null);
    throw new Error(error?.detail || 'Failed to save config');
  }
  return res.json();
}
