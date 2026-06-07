using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using FaceRecognition.Desktop.Models;

namespace FaceRecognition.Desktop.Services;

public sealed class BackendProcessManager
{
    private Process? _process;
    private DesktopConfig? _config;
    private string? _logFile;

    public async Task<BackendRuntimeInfo> StartAsync()
    {
        _config = DesktopConfigLoader.Load();
        ValidateConfigPaths(_config);

        var port = _config.Backend.Port == 0 ? PortFinder.FindFreeTcpPort() : _config.Backend.Port;
        
        var shellLogsDir = AppPaths.LogsPath;
        Directory.CreateDirectory(shellLogsDir);
        var shellLogFile = Path.Combine(shellLogsDir, "app.log");

        var runtimeLogsDir = _config.Runtime.LogsDir;
        Directory.CreateDirectory(runtimeLogsDir);
        _logFile = Path.Combine(runtimeLogsDir, "backend.log");

        File.AppendAllText(shellLogFile, $"Using config file: {AppPaths.ConfigPath}\n");

        var psi = new ProcessStartInfo
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };

        if (File.Exists(AppPaths.BackendExePath))
        {
            psi.FileName = AppPaths.BackendExePath;
            psi.WorkingDirectory = Path.GetDirectoryName(AppPaths.BackendExePath)!;
            File.AppendAllText(_logFile, $"Using packaged backend: {psi.FileName}\n");
            File.AppendAllText(shellLogFile, $"Using packaged backend: {psi.FileName}\n");
        }
        else
        {
            if (AppPaths.BackendDevScript == null || !File.Exists(AppPaths.BackendDevScript))
            {
                throw new FileNotFoundException("Phase 2A requires repo backend fallback (backend/main.py) or a compiled FaceBackend.exe. Neither was found.");
            }
            
            psi.FileName = "python";
            psi.Arguments = AppPaths.BackendDevScript;
            psi.WorkingDirectory = AppPaths.BackendDevDir!;
            File.AppendAllText(_logFile, $"Using repository backend fallback: {psi.Arguments}\n");
            File.AppendAllText(shellLogFile, $"Using repository backend fallback: {psi.Arguments}\n");
        }

        File.AppendAllText(_logFile, $"Runtime baseDir: {_config.Runtime.BaseDir}\n");
        File.AppendAllText(_logFile, $"Selected backend port: {port}\n");

        ConfigureEnvironment(psi, _config, port);

        _process = Process.Start(psi) 
            ?? throw new InvalidOperationException("Could not start backend process.");

        _ = Task.Run(() => PipeOutputToFileAsync(_process, _logFile));

        var apiBaseUrl = $"http://127.0.0.1:{port}/api";
        await WaitForHealthAsync(port);

        return new BackendRuntimeInfo
        {
            Port = port,
            ApiBaseUrl = apiBaseUrl,
            Process = _process
        };
    }

    private void ValidateConfigPaths(DesktopConfig config)
    {
        var shellLogFile = Path.Combine(AppPaths.LogsPath, "app.log");
        
        // Fatal checks: Ensure we can create internal app directories
        Directory.CreateDirectory(config.Runtime.JobsDir);
        Directory.CreateDirectory(config.Runtime.LogsDir);

        // Non-fatal checks: Log missing external data paths but allow startup
        LogIfMissing(config.Runtime.BaseDir, "Base directory (baseDir)", shellLogFile);
        LogIfMissing(config.Runtime.ActorsDir, "Actors directory (actorsDir)", shellLogFile);
        LogIfMissing(config.Runtime.ModelsDir, "Models directory (modelsDir)", shellLogFile);
        LogIfMissing(config.Runtime.FaissIndexDir, "FAISS index directory (faissIndexDir)", shellLogFile);
        
        var faissFile = Path.Combine(config.Runtime.FaissIndexDir, "face_index.faiss");
        if (!File.Exists(faissFile))
        {
            File.AppendAllText(shellLogFile, $"[Warning] FAISS index file not found at {faissFile}\n");
        }

        LogIfMissing(config.Runtime.VideosDir, "Videos directory", shellLogFile);
    }

    private void LogIfMissing(string path, string description, string logFile)
    {
        if (!Directory.Exists(path))
        {
            File.AppendAllText(logFile, $"[Warning] {description} not found at {path}\n");
        }
    }

    private async Task PipeOutputToFileAsync(Process process, string logFile)
    {
        using var streamWriter = new StreamWriter(logFile, append: true) { AutoFlush = true };
        
        process.OutputDataReceived += (s, e) => { if (e.Data != null) streamWriter.WriteLine(e.Data); };
        process.ErrorDataReceived += (s, e) => { if (e.Data != null) streamWriter.WriteLine(e.Data); };
        
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        
        await process.WaitForExitAsync();
    }

    private async Task WaitForHealthAsync(int port)
    {
        using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(5) };
        var url = $"http://127.0.0.1:{port}/api/health";
        
        var sw = Stopwatch.StartNew();
        while (sw.Elapsed < TimeSpan.FromSeconds(90))
        {
            if (_process != null && _process.HasExited)
            {
                throw new Exception($"Backend process exited unexpectedly with code {_process.ExitCode}");
            }

            try
            {
                var response = await client.GetAsync(url);
                if (response.IsSuccessStatusCode)
                    return;
            }
            catch
            {
                // Ignore connection errors while waiting
            }
            await Task.Delay(150);
        }
        throw new TimeoutException("Backend health check timed out after 90 seconds.");
    }

    public void Stop()
    {
        if (_process == null || _process.HasExited)
            return;

        try
        {
            _process.CloseMainWindow();
            if (!_process.WaitForExit(3000))
            {
                _process.Kill(entireProcessTree: true);
            }
        }
        catch
        {
            try { _process.Kill(entireProcessTree: true); } catch { /* ignore */ }
        }

        if (_logFile != null)
        {
            try 
            {
                File.AppendAllText(_logFile, "Backend process stopped.\n");
            } 
            catch { /* ignore */ }
        }
    }

    internal void ConfigureEnvironment(ProcessStartInfo psi, DesktopConfig config, int port)
    {
        psi.Environment["HOST"] = "127.0.0.1";
        psi.Environment["PORT"] = port.ToString();
        psi.Environment["DESKTOP_MODE"] = "true";
        psi.Environment["PYTHONIOENCODING"] = "utf-8";
        
        psi.Environment["CONFIG_PATH"] = AppPaths.ConfigPath;
        psi.Environment["BASE_DIR"] = config.Runtime.BaseDir;
        psi.Environment["ACTORS_DIR"] = config.Runtime.ActorsDir;
        psi.Environment["MODELS_DIR"] = config.Runtime.ModelsDir;
        psi.Environment["FAISS_INDEX_DIR"] = config.Runtime.FaissIndexDir;
        psi.Environment["VIDEOS_DIR"] = config.Runtime.VideosDir;
        psi.Environment["JOBS_DIR"] = config.Runtime.JobsDir;
        psi.Environment["LOGS_DIR"] = config.Runtime.LogsDir;
        
        psi.Environment["CORS_ORIGINS"] = JsonSerializer.Serialize(config.Backend.CorsOrigins);
        psi.Environment["FACE_EXECUTION_PROVIDERS"] = JsonSerializer.Serialize(config.Ai.FaceExecutionProviders);
        psi.Environment["FACE_MODEL_NAME"] = config.Ai.FaceModelName;
    }
}
