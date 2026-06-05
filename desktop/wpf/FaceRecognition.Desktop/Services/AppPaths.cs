using System;
using System.IO;

namespace FaceRecognition.Desktop.Services;

public static class AppPaths
{
    public static string ExecutableRoot => AppContext.BaseDirectory;

    public static string? RepoRoot 
    {
        get
        {
            var current = ExecutableRoot;
            while (!string.IsNullOrEmpty(current))
            {
                var mainPy = Path.Combine(current, "backend", "main.py");
                var pkgJson = Path.Combine(current, "frontend", "package.json");
                if (File.Exists(mainPy) && File.Exists(pkgJson))
                {
                    return current;
                }
                
                var parent = Directory.GetParent(current);
                if (parent == null) break;
                current = parent.FullName;
            }
            return null; // Not running from or inside a repo
        }
    }

    public static string BackendExePath => Path.Combine(ExecutableRoot, "backend", "FaceBackend.exe");
    
    public static string? BackendDevScript => RepoRoot != null ? Path.Combine(RepoRoot, "backend", "main.py") : null;
    public static string? BackendDevDir => RepoRoot != null ? Path.Combine(RepoRoot, "backend") : null;

    public static string FrontendDistPath 
    {
        get
        {
            var localDist = Path.Combine(ExecutableRoot, "frontend", "dist");
            if (File.Exists(Path.Combine(localDist, "index.html")))
            {
                return localDist;
            }

            if (RepoRoot != null)
            {
                return Path.Combine(RepoRoot, "frontend", "dist");
            }

            return localDist; // Fallback to local even if missing, MainWindow will handle it
        }
    }
    
    public static string FrontendIndexPath => Path.Combine(FrontendDistPath, "index.html");

    public static string LogsPath => Path.Combine(ExecutableRoot, "logs");
    
    // We leave data paths unchanged, as the user said "Do not replace hardcoded D:\FaceService paths yet", but AppPaths had some defaults.
    public static string DataPath => Path.Combine(ExecutableRoot, "data");
    public static string ModelsPath => Path.Combine(ExecutableRoot, "models");
    public static string ConfigPath
    {
        get
        {
            var localConfig = Path.Combine(ExecutableRoot, "config.json");
            if (File.Exists(localConfig)) return localConfig;
            
            if (RepoRoot != null && File.Exists(Path.Combine(RepoRoot, "config.json")))
            {
                return Path.Combine(RepoRoot, "config.json");
            }
            return localConfig; // Default to local for creation
        }
    }
    
    public static string ConfigExamplePath => Path.Combine(ExecutableRoot, "config.example.json");
}
