export interface FaceMatch {
  actor_id: number
  actor_name: string
  confidence: number
  face_bbox: number[]
  actor_image_url?: string | null
}

export interface UploadResponse {
  image_id: string
  filename: string
  faces_detected: number
  matches: FaceMatch[]
  closest_matches: FaceMatch[]
  all_faces?: number[][]
  processing_time_ms: number
  preview_url?: string
}

export interface BatchUploadResponse {
  results: UploadResponse[]
}

export interface Actor {
  id: number
  stashdb_id: string | null
  name: string
  birth_year: number | null
  birthdate: string | null
  gender: string | null
  aliases: string[]
  scene_count: number | null
  breast_type: string | null
  height_cm: number | null
  measurements: string | null
  cup_size: string | null
  band_size: number | null
  waist_size: number | null
  hip_size: number | null
  country: string | null
  ethnicity: string | null
  eye_color: string | null
  hair_color: string | null
  tattoos: string[]
  piercings: string[]
  career_start_year: number | null
  career_end_year: number | null
  image_url: string | null
  stashdb_urls: string[]
  bio: string | null
  filmography: string | null
  tags: string[]
  reference_image_count: number
  preview_image_url: string | null
  reference_images: ActorImage[]
  created_at: string
  updated_at: string
}

export interface ActorImage {
  id: number
  filename: string
  url: string
  created_at: string | null
}

export interface ActorListResponse {
  actors: Actor[]
  total: number
  page: number
  page_size: number
}

export interface HealthStatus {
  status: string
  actors_count: number
  index_size: number
  faiss_available: boolean
  model_loaded: boolean
}

export interface Video {
  id: number
  filepath: string
  filename: string
  duration: number | null
  size_bytes: number | null
  status: 'unprocessed' | 'processing' | 'completed' | 'failed'
  error_message: string | null
  progress?: number
  stashdb_scene_id?: string | null
  created_at: string
  updated_at: string
  actors?: Array<{ id: number; name: string }>
  detections?: VideoDetection[]
}

export interface VideoDetection {
  id: number
  video_id: number
  actor_id: number
  actor_name: string
  timestamp: number
  bbox: number[]
  confidence: number
}

