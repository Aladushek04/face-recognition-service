using System;
using System.IO;
using System.Text.Json;
using FaceRecognition.Desktop.Models;

namespace FaceRecognition.Desktop.Services;

public static class DesktopConfigLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    public static DesktopConfig Load()
    {
        var configPath = AppPaths.ConfigPath;

        if (File.Exists(configPath))
        {
            try
            {
                var json = File.ReadAllText(configPath);
                var config = JsonSerializer.Deserialize<DesktopConfig>(json, JsonOptions);
                config ??= new DesktopConfig();
                
                ValidateAndFallbackPaths(config);
                return config;
            }
            catch (Exception ex)
            {
                // Fallback to default if there's a parsing error, but log it
                File.AppendAllText(Path.Combine(AppPaths.LogsPath, "app.log"), $"[Error] Failed to load config from {configPath}: {ex.Message}\n");
                return new DesktopConfig();
            }
        }

        // If it doesn't exist, create it with default values for backward compatibility
        var defaultConfig = new DesktopConfig();
        try
        {
            var json = JsonSerializer.Serialize(defaultConfig, JsonOptions);
            File.WriteAllText(configPath, json);
        }
        catch (Exception ex)
        {
            File.AppendAllText(Path.Combine(AppPaths.LogsPath, "app.log"), $"[Error] Failed to write default config to {configPath}: {ex.Message}\n");
        }

        ValidateAndFallbackPaths(defaultConfig);
        return defaultConfig;
    }

    internal static void ValidateAndFallbackPaths(DesktopConfig config)
    {
        if (config.Runtime != null)
        {
            config.Runtime.JobsDir = AppPaths.LocalJobsDir;
            config.Runtime.LogsDir = AppPaths.LogsPath;
        }
    }
}
