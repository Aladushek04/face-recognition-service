# Face Recognition Service

A local, self-hosted face recognition service for identifying actors/actresses from uploaded photos and videos. Face detection, embeddings, vector search, and database storage run locally; optional integrations such as StashDB use network APIs only when configured.

## Features

- **Face Detection & Recognition**: Uses insightface with ArcFace embeddings for high-accuracy face matching
- **Vector Search**: FAISS (Facebook AI Similarity Search) for fast, efficient similarity search
- **StashDB Ingestion**: Scrape and import performer cards, download profile photos, and automatically build FAISS embeddings
- **Persistent Face Assignment**: Interactively link face crop coordinates from uploaded photos to new or existing actors
- **Material 3 Interface**: Modern design conforming to Material 3 specs (shapes, dark mode, spacious stacked comparison view)
- **Bilingual Localization**: Full English and Russian language toggle support (EN/RU)
- **REST API**: Full API for programmatic access (see API docs at `/docs`)
- **Local ML Processing**: Face recognition runs on your machine; optional metadata imports can call external APIs
- **Privacy-First**: All images and data stay on your machine

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Web Browser                         │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │  Upload Zone │    │ Results Panel│    │Actors DB  │ │
│  └─────────────┘    └──────────────┘    └───────────┘ │
└──────────────────────────┬────────────────────────────┘
                           │ HTTP/REST
┌──────────────────────────▼────────────────────────────┐
│              FastAPI Backend (Python)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ Upload Route │  │ Actor Route  │  │ Health     │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┘  │
│         │                  │                            │
│  ┌──────▼──────────────────▼───────────────────────┐  │
│  │           Core Services                          │  │
│  │  ┌─────────────┐  ┌──────────────┐             │  │
│  │  │ FaceDetector │  │ VectorStore  │             │  │
│  │  │ (insightface)│  │ (FAISS)      │             │  │
│  │  └─────────────┘  └──────┬───────┘             │  │
│  └──────────────────────────┬─────────────────────┘  │
└─────────────────────────────┼────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────┐
│                  Local Storage                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ SQLite   │  │ FAISS    │  │ Actor Images     │   │
│  │ (metadata)│  │ (index)  │  │ (data/actors/)   │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- 4GB+ RAM recommended
- GPU (optional, for faster inference)

### 1. Clone and Setup

```bash
cd face-recognition-service
```

### 2. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies

```bash
cd ../frontend
npm install
```

### 4. Configure

```bash
cd ..
cp .env.example .env
# Edit .env as needed
```

Runtime data can be kept outside the repository, which is useful when actor images, FAISS indexes, model files, and videos live on a larger HDD:

```env
BASE_DIR=D:\FaceService
ACTORS_DIR=D:\FaceService\actors
FAISS_INDEX_DIR=D:\FaceService\data\faiss_index
VIDEOS_DIR=D:\Videos
```

### 5. Seed Demo Actors

```bash
cd ..
python scripts/seed_actors.py
```

This adds 5 demo actors to the database. You'll need to add reference photos.

### 6. Import Actors from StashDB (Optional)

Add your StashDB token to `.env`:

```bash
STASHDB_API_URL=https://stashdb.org/graphql
STASHDB_API_KEY=your-token-here
```

Then import performer metadata and profile images:

```bash
python scripts/scrape_stashdb.py --limit 50
```

Useful options:

```bash
python scripts/scrape_stashdb.py --query "Jane" --limit 20
python scripts/scrape_stashdb.py --limit 200 --page-size 50 --no-images
python scripts/scrape_stashdb.py --limit 10 --dry-run
```

After importing images, rebuild the FAISS index with `python scripts/build_index.py`.

### 7. Add Reference Photos

For each actor, add clear, front-facing photos to:
```
data/actors/<Actor_Name>/
```

Example:
```
data/actors/Tom_Hanks/
├── tom_hanks_1.jpg
├── tom_hanks_2.jpg
└── tom_hanks_3.jpg
```

**Tips for best results:**
- Use clear, well-lit photos
- Front-facing or slight angle (±30°)
- No sunglasses or heavy shadows
- 3-5 reference photos per actor recommended

### 8. Build the Index

```bash
python scripts/build_index.py
```

This scans all actor images, extracts face embeddings, and builds the FAISS index.

The matcher can use several reference embeddings for the same actor. Add
multiple visually different photos per actor, then re-run the index build after
adding or replacing photos. Use `--refresh-cache` to regenerate every cached
embedding:

```bash
python scripts/build_index.py --refresh-cache
```

Video analysis also has an optional fallback pass. If the first pass finds too
few confirmed actors, the service scans the same video with a shorter frame step
and a softer recognition threshold, then requires more repeated hits before
saving detections. This does not require rebuilding the FAISS index.

### 9. Start the Services

**Backend:**
```bash
cd backend
python main.py
# Server starts at http://localhost:8000
# API docs at http://localhost:8000/docs
```

**Frontend (in a new terminal):**
```bash
cd frontend
npm run dev
# Frontend at http://localhost:3000
```

### Docker Setup (Alternative)

```bash
docker-compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## Usage

### Web UI

1. Open `http://localhost:3000`
2. Drag and drop photos or click to browse
3. View match results with confidence scores
4. Manage your actor database via the "Actor Database" tab

### API

#### Upload an Image
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@photo.jpg"
```

#### Batch Upload
```bash
curl -X POST http://localhost:8000/api/upload/batch \
  -F "files=@photo1.jpg" \
  -F "files=@photo2.jpg"
```

#### List Actors
```bash
curl http://localhost:8000/api/actors?page=1&page_size=20
```

#### Add Actor
```bash
curl -X POST http://localhost:8000/api/actors \
  -F "name=John Doe" \
  -F "birth_year=1980" \
  -F "gender=male" \
  -F "bio=Actor biography" \
  -F "tags=actor,hollywood"
```

#### Add Reference Image
```bash
curl -X POST http://localhost:8000/api/actors/1/images \
  -F "file=@reference.jpg"
```

#### Health Check
```bash
curl http://localhost:8000/api/health
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload single image |
| POST | `/api/upload/batch` | Upload multiple images |
| GET | `/api/uploads/{image_id}` | Retrieve persistently cached uploaded image |
| POST | `/api/uploads/{image_id}/assign` | Assign face coordinates from uploaded image to actor |
| GET | `/api/actors` | List actors (paginated) |
| GET | `/api/actors/{id}` | Get actor details |
| POST | `/api/actors` | Create new actor |
| PUT | `/api/actors/{id}` | Update actor |
| DELETE | `/api/actors/{id}` | Delete actor |
| POST | `/api/actors/{id}/images` | Add reference image |
| GET | `/api/health` | Health check |

Full interactive API docs: `http://localhost:8000/docs`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `CORS_ORIGINS` | `["http://localhost:3000","http://127.0.0.1:3000"]` | Browser origins allowed to call the API |
| `BASE_DIR` | project root | Runtime data root for uploads, DB, embeddings, thumbnails, and models |
| `ACTORS_DIR` | `<BASE_DIR>/data/actors` | Reference image directory |
| `FAISS_INDEX_DIR` | `<BASE_DIR>/data/faiss_index` | FAISS index directory |
| `VIDEOS_DIR` | `D:\Videos` | Directory scanned by the video media center |
| `FACE_RECOGNITION_THRESHOLD` | `0.65` | Min confidence for matches |
| `FAISS_INDEX_TYPE` | `HNSW32` | Index type (HNSW32, IVFFlat, Flat) |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max upload size |

## Performance

| Metric | Value |
|--------|-------|
| Face detection | ~50-200ms per image (CPU) |
| Embedding extraction | ~20-50ms per face |
| Vector search | ~1-5ms per query |
| Total processing | ~100-500ms per image |

**GPU acceleration**: Install `faiss-gpu` and `onnxruntime-gpu` for 5-10x speedup.

## Building Your Actor Database

### Data Sources

1. **Manual Collection**: Download public photos from official sources
2. **Wikipedia**: Many actor pages have freely licensed images
3. **IMDb**: Public photos from filmographies
4. **Public Datasets**: Consider datasets like:
   - CelebA (research use)
   - FFHQ (research use)
   - VGGFace2 (research use)

### Best Practices

- Use **high-quality, clear photos** for reference images
- Include **multiple angles** per actor (3-5 recommended)
- Avoid **group photos** or **heavily edited images**
- **Consistent lighting** improves accuracy
- **Recent photos** work better for current actors

## Privacy

- ✅ Face detection, embeddings, vector search, and video analysis are local
- ✅ No images uploaded to any server
- ✅ External API calls are optional and require configured integrations such as StashDB
- ✅ Database stored locally (SQLite)
- ✅ Models cached locally after first download

## Troubleshooting

### Model not loading
```bash
# Re-download insightface models
python -c "from insightface.app import FaceAnalysis; app = FaceAnalysis(name='antelopev2'); app.prepare(ctx_id=0)"
```

### FAISS index corrupted
```bash
# Rebuild from scratch
rm data/faiss_index/*
python scripts/build_index.py
```

### Low recognition accuracy
- Add more reference images per actor
- Use clearer, front-facing photos
- Lower the `FACE_RECOGNITION_THRESHOLD` in `.env`
- Try different FAISS index type (Flat for max accuracy)

## Project Structure

```
face-recognition-service/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration
│   ├── models.py            # Pydantic schemas
│   ├── models/
│   │   ├── face_detector.py # Face detection & embeddings
│   │   └── vector_store.py  # FAISS index management
│   ├── database/
│   │   ├── schema.py        # DB schema
│   │   └── actor_db.py      # Database operations
│   ├── routes/
│   │   ├── upload.py        # Upload endpoints
│   │   └── actors.py        # Actor management
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── lib/             # API client
│   │   ├── types/           # TypeScript types
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── actors/              # Actor reference images
│   ├── faiss_index/         # FAISS index files
│   ├── uploads/             # Persistent uploaded image cache
│   └── db/                  # SQLite database
├── scripts/
│   ├── seed_actors.py       # Seed demo actors
│   └── build_index.py       # Build FAISS index
├── docker-compose.yml
├── .env.example
├── MATERIAL3_CHECKLIST.md   # Design validation guidelines
├── README.md
```

## License

MIT
