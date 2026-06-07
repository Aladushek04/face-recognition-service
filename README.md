# Face Recognition Service

A local service for facial recognition of actors in photos and videos. The database of actors, images, embeddings, FAISS index, and video metadata are stored locally. StashDB is optionally used as an external source for metadata and images if an API key is provided.

## 🚀 Key Features
- **Local Desktop UI**: Embedded Chromium shell via WebView2.
- **Offline ML**: Bundled hidden PyInstaller FastAPI backend with GPU (CUDA) and CPU support.
- **Smart Directory Management**: Writable configurations (`config.json`), jobs, and logs are kept in safe local paths (`%LOCALAPPDATA%\Programs\Face Recognition Service`), while massive ML data and video files reside on user-defined drives.
- **Safe Setup Mode**: Installer starts the app with safe, empty defaults that require manual first-run configuration.
- **Maintenance Center**: In-app UI for managing FAISS indexing, actor/image cleanup, and StashDB backfills as background jobs.

## 📥 Installation

1. Download the latest release artifact (e.g., `FaceRecognitionService-Setup-v1.0.0-rc1.exe` or the final renamed `FaceRecognitionService-Setup-v1.0.0.exe`) from the Releases page.
2. Ensure you have the required runtimes installed (the installer will automatically prompt you if they are missing):
   - **Microsoft .NET 10 Desktop Runtime (x64)**
   - **Microsoft Edge WebView2 Runtime**
3. Run the setup executable. The application will install per-user into `%LOCALAPPDATA%\Programs\Face Recognition Service`.
4. Launch the application from your Start Menu.
5. On your first launch, the app will display a **Configuration Required** screen.

> **Note**: No Python environment, Node.js, or source repository is required on the user machine. The backend runs completely bundled as `FaceBackend.exe`. The app cleanly manages its child processes and leaves no orphans when closed.

## ⚙️ First-Run Configuration

By default, the installer deploys a safe `config.example.json` with empty external paths. You must configure these through the app Settings before the AI can initialize.

1. Go to **Settings**.
2. Point the directories to your external massive storage drives. Expected production paths might look like:
   - **Base Directory**: `D:\FaceService`
   - **Actors Directory**: `D:\FaceService\actors`
   - **Models Directory**: `D:\FaceService\models`
   - **FAISS Index Directory**: `D:\FaceService\data\faiss_index`
   - **Videos Directory**: `D:\Videos`
3. Click **Validate**. If validation succeeds, click **Save** and restart the app when prompted.
4. You should see `Model Ready` with the number of loaded actors and vectors, indicating successful initialization.

### Configuration & Update Policy
- `config.json` is safely preserved during reinstalls and version upgrades.
- `config.example.json` is refreshed during upgrades to provide the newest schema.
- Runtime application logs and background maintenance jobs are stored safely in your installation directory (`%LOCALAPPDATA%\Programs\Face Recognition Service\logs` and `\data\jobs`).

## 💻 GPU Support

NVIDIA GPUs are fully supported for accelerated face detection and embedding extraction via the `CUDAExecutionProvider`.
- If a compatible NVIDIA GPU and driver are found, they will be utilized automatically.
- **No external CUDA Toolkit installation is required**, as the necessary libraries are bundled.
- If no GPU is available, the backend safely falls back to CPU execution (`CPUExecutionProvider`).

---

## 🛠️ Developer Guide (Running from Source)

The following instructions are only for developers who wish to modify the source code.

### Стек
- Backend: FastAPI, SQLite, InsightFace, ONNX Runtime, OpenCV, FAISS.
- Frontend: React 18, Vite, TypeScript, Tailwind CSS, Zustand, lucide-react.
- Desktop Shell: WPF (.NET 10), WebView2.

### Требования для разработки
- Windows или Linux.
- Python 3.10+.
- Node.js 18+.

### Быстрый старт из исходников
1. Установите backend-зависимости:
```powershell
cd backend
python -m pip install -r requirements.txt
```

2. Установите frontend-зависимости:
```powershell
cd frontend
npm install
```

3. Создайте `.env` из примера:
```powershell
copy .env.example .env
```

4. Отредактируйте `.env`. Минимально проверьте пути:
```env
BASE_DIR=D:\FaceService
ACTORS_DIR=D:\FaceService\actors
FAISS_INDEX_DIR=D:\FaceService\data\faiss_index
VIDEOS_DIR=D:\Videos
```

5. Запустите WPF Desktop Shell:
```powershell
dotnet run --project desktop\wpf\FaceRecognition.Desktop\FaceRecognition.Desktop.csproj
```
- Web UI: `http://127.0.0.1:3000` (если запущен Docker или frontend отдельно)
- API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

### Конфигурация `.env` (Source)

Основные параметры:
```env
HOST=0.0.0.0
PORT=8000
DEBUG=false
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]

BASE_DIR=D:\FaceService
ACTORS_DIR=D:\FaceService\actors
FAISS_INDEX_DIR=D:\FaceService\data\faiss_index
VIDEOS_DIR=D:\Videos

FACE_RECOGNITION_THRESHOLD=0.65
VIDEO_FACE_RECOGNITION_THRESHOLD=0.55
CONCURRENT_VIDEO_LIMIT=1

STASHDB_API_URL=https://stashdb.org/graphql
STASHDB_API_KEY=
```

Важные пути:

- `BASE_DIR`: корень runtime-данных.
- `ACTORS_DIR`: папки актеров и reference-фото.
- `FAISS_INDEX_DIR`: `face_index.faiss` и `face_index_ids.pkl`.
- `VIDEOS_DIR`: папка, которую сканирует видео-раздел.

Для GPU после установки подходящего ONNX Runtime можно включить:

```env
FACE_EXECUTION_PROVIDERS=["CUDAExecutionProvider","CPUExecutionProvider"]
```

## База актеров и фото

Каждый актер хранится в SQLite, а reference-фото лежат в папке:

```text
%ACTORS_DIR%\<Actor_Name>\
```

Фото можно добавлять через UI. Backend сразу пытается извлечь faces, кеширует embeddings и обновляет FAISS-индекс динамически.

Если фото добавлялись вручную в файловую систему, пересоберите индекс:

```powershell
python scripts\build_index.py
```

По умолчанию индексатор пропускает актеров, у которых меньше 4 reference-фото. Это снижает шум от слабых профилей. Чтобы изменить порог:

```powershell
python scripts\build_index.py --min-images 4
python scripts\build_index.py --min-images 1
```

Индексатор читает reference-фото пачками и по умолчанию не печатает каждого пропущенного актера. Для подробного списка пропусков:

```powershell
python scripts\build_index.py --verbose-skips
```

Полная пересборка embeddings:

```powershell
python scripts\build_index.py --refresh-cache
```

## StashDB импорт

Добавьте ключ в `.env`:

```env
STASHDB_API_KEY=your-token-here
```

Одиночный импорт доступен в UI через поиск StashDB. Массовый импорт и другие операции очистки удобнее запускать через раздел Maintenance Jobs в приложении.

Прямой запуск скраппера:

```powershell
python scripts\scrape_stashdb.py --country-region preferred-map --gender female --breast-type augmented --min-scenes 10 --require-image --image-count 3 --image-order last --validate-image-faces --limit 200
```

Страновые пресеты:

- `--country-region preferred-map`: основной пресет по выбранной карте, оставляет зеленые страны и отсекает красные зоны.
- `--country-region americas-europe-russia`: более строгий пресет, только Северная/Южная Америка, Европа и Россия.

Дополнительные параметры стран:

```powershell
--include-countries Australia,New Zealand
--exclude-countries Turkey,Kazakhstan
--allow-unknown-country
```

Без `--allow-unknown-country` профили с пустой страной пропускаются, если включен страновой фильтр.

Полезные варианты:

```powershell
python scripts\scrape_stashdb.py --limit 50 --dry-run
python scripts\scrape_stashdb.py --query "Jane" --limit 20
python scripts\scrape_stashdb.py --all --no-images --update-existing
python scripts\scrape_stashdb.py --resume-page 25 --country-region preferred-map
```

После массового импорта, если скрипт не индексировал все нужное динамически, пересоберите FAISS:

```powershell
python scripts\build_index.py
```

## Видео

Видео-раздел работает с папкой `VIDEOS_DIR`.

1. Положите видео в `VIDEOS_DIR`.
2. В UI нажмите scan, либо вызовите API `POST /api/videos/scan`.
3. Запустите обработку одного видео или всех unprocessed/failed.
4. После обработки UI показывает найденных актеров и таймлайн detections.

Поддерживаемые расширения:

```text
.mp4 .mkv .avi .mov .webm .flv .m4v .wmv .ts
```

Видео можно:

- просматривать через backend stream endpoint;
- переименовывать из UI;
- вручную добавлять или удалять актеров из видео;
- искать кандидатов StashDB;
- привязывать StashDB scene по кандидату или URL;
- скачивать StashDB cover в thumbnails.

Видео-распознавание использует отдельные thresholds из `.env`, включая fallback pass:

```env
VIDEO_FRAME_STEP=1.0
VIDEO_FACE_RECOGNITION_THRESHOLD=0.55
VIDEO_MIN_ACTOR_HITS=2
VIDEO_FALLBACK_ENABLED=true
VIDEO_FALLBACK_FRAME_STEP=0.5
VIDEO_FALLBACK_FACE_RECOGNITION_THRESHOLD=0.48
VIDEO_FALLBACK_MIN_ACTOR_HITS=3
```

## Очистка данных

Все опасные cleanup-скрипты по умолчанию запускаются как dry-run. Реальное удаление включается только через `--apply`.

Проверить актеров, которые не проходят фильтры:

```powershell
python scripts\cleanup_actors.py --gender female --breast-type augmented --min-scenes 10 --min-birth-year 1960 --require-image
```

Проверить актеров вне выбранной карты стран:

```powershell
python scripts\cleanup_actors.py --country-region preferred-map
```

Комбинированный preview для удаления шлака по качеству профиля и стране:

```powershell
python scripts\cleanup_actors.py --country-region preferred-map --gender female --breast-type augmented --min-scenes 10 --min-birth-year 1960 --require-image
```

Удалить найденных кандидатов:

```powershell
python scripts\cleanup_actors.py --country-region preferred-map --gender female --breast-type augmented --min-scenes 10 --min-birth-year 1960 --require-image --apply
```

Проверить reference-фото без пригодного лица:

```powershell
python scripts\cleanup_images.py --min-face-area-ratio 0.01
```

Удалить плохие фото и DB-строки:

```powershell
python scripts\cleanup_images.py --min-face-area-ratio 0.01 --delete-missing --apply
```

После cleanup обычно нужно пересобрать FAISS:

```powershell
python scripts\build_index.py
```

## API

Основная документация доступна после запуска backend:

```text
http://127.0.0.1:8000/docs
```

Ключевые endpoints:

```text
GET  /api/health
GET  /api/index/status
POST /api/index/rebuild

GET  /api/tools/jobs
GET  /api/tools/jobs/{job_id}
GET  /api/tools/jobs/{job_id}/logs
POST /api/tools/jobs/{job_type}
POST /api/tools/jobs/{job_id}/cancel

POST /api/upload
POST /api/upload/batch
GET  /api/uploads/{image_id}
POST /api/uploads/{image_id}/assign

GET    /api/actors
GET    /api/actors/{actor_id}
POST   /api/actors
PUT    /api/actors/{actor_id}
DELETE /api/actors/{actor_id}
POST   /api/actors/{actor_id}/images
GET    /api/actors/{actor_id}/images/{image_id}
DELETE /api/actors/{actor_id}/images/{image_id}

GET  /api/stashdb/search
POST /api/stashdb/import

GET    /api/videos
GET    /api/videos/{video_id}
POST   /api/videos/scan
POST   /api/videos/{video_id}/process
POST   /api/videos/process-unprocessed
GET    /api/videos/{video_id}/stream
POST   /api/videos/{video_id}/rename
DELETE /api/videos/{video_id}
POST   /api/videos/{video_id}/match-stashdb
POST   /api/videos/{video_id}/search-stashdb
POST   /api/videos/{video_id}/link-stashdb
POST   /api/videos/{video_id}/link-stashdb-url
POST   /api/videos/{video_id}/actors/{actor_id}
DELETE /api/videos/{video_id}/actors/{actor_id}
```

Пример загрузки фото:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/upload -F "file=@photo.jpg"
```

Пример пересборки индекса через API:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/index/rebuild?refresh_cache=false"
```

Maintenance jobs API examples are documented in:

```text
docs/MAINTENANCE_JOB_API.md
```

Quick dry-run example:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/cleanup_actors -H "Content-Type: application/json" -d "{\"args\":[\"--require-image\",\"--include-unknown\"]}"
```

Quick apply example:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/tools/jobs/cleanup_actors -H "Content-Type: application/json" -d "{\"apply\":true,\"args\":[\"--require-image\",\"--include-unknown\"]}"
```

## Docker

Docker-конфигурация есть, но локальный Windows-запуск сейчас основной и проще для работы с большими папками видео/актеров.

Запуск:

```powershell
docker compose up --build
```

Backend будет на `http://localhost:8000`, frontend на `http://localhost:3000`.

Проверьте volume/path mapping перед использованием с внешними папками. В `docker-compose.yml` по умолчанию монтируется локальная `./data` в `/app/data`.

## Хранение данных

Типовые runtime-файлы:

```text
%BASE_DIR%\data\db\actors.db
%ACTORS_DIR%\...
%BASE_DIR%\data\embeddings\actor_image_*.npy
%FAISS_INDEX_DIR%\face_index.faiss
%FAISS_INDEX_DIR%\face_index_ids.pkl
%BASE_DIR%\data\uploads\...
%BASE_DIR%\thumbnails\...
%BASE_DIR%\models\...
```

Не храните StashDB API key в скриптах. Держите его только в `.env`.

## Частые проблемы

`frontend/node_modules is missing`

Запустите:

```powershell
cd frontend
npm install
```

`Face detection model not loaded`

Проверьте установку `insightface` и ONNX Runtime. Для CPU используйте `onnxruntime`, для NVIDIA GPU используйте совместимый `onnxruntime-gpu` и CUDA stack.

`No actors found` или `index_size = 0`

Добавьте актеров и reference-фото, затем выполните:

```powershell
python scripts\build_index.py
```

Видео не появляются после scan

Проверьте `VIDEOS_DIR` в `.env`, существование папки и расширения файлов.

StashDB не работает

Проверьте:

```env
STASHDB_API_URL=https://stashdb.org/graphql
STASHDB_API_KEY=...
```

Если массовый скраппер прервался, используйте напечатанный `--resume-page`.
