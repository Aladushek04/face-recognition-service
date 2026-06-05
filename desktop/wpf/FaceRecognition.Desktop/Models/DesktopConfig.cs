using System.Text.Json.Serialization;

namespace FaceRecognition.Desktop.Models;

public class DesktopConfig
{
    [JsonPropertyName("schemaVersion")]
    public int SchemaVersion { get; set; } = 1;

    [JsonPropertyName("runtime")]
    public RuntimeConfig Runtime { get; set; } = new();

    [JsonPropertyName("backend")]
    public BackendConfig Backend { get; set; } = new();

    [JsonPropertyName("ai")]
    public AiConfig Ai { get; set; } = new();
}

public class RuntimeConfig
{
    [JsonPropertyName("baseDir")]
    public string BaseDir { get; set; } = @"D:\FaceService";

    [JsonPropertyName("actorsDir")]
    public string ActorsDir { get; set; } = @"D:\FaceService\actors";

    [JsonPropertyName("modelsDir")]
    public string ModelsDir { get; set; } = @"D:\FaceService\models";

    [JsonPropertyName("faissIndexDir")]
    public string FaissIndexDir { get; set; } = @"D:\FaceService\data\faiss_index";

    [JsonPropertyName("videosDir")]
    public string VideosDir { get; set; } = @"D:\Videos";

    [JsonPropertyName("jobsDir")]
    public string JobsDir { get; set; } = Services.AppPaths.LocalJobsDir;

    [JsonPropertyName("logsDir")]
    public string LogsDir { get; set; } = Services.AppPaths.LogsPath;
}

public class BackendConfig
{
    [JsonPropertyName("host")]
    public string Host { get; set; } = "127.0.0.1";

    [JsonPropertyName("port")]
    public int Port { get; set; } = 0;

    [JsonPropertyName("desktopMode")]
    public bool DesktopMode { get; set; } = true;

    [JsonPropertyName("corsOrigins")]
    public string[] CorsOrigins { get; set; } = new[] 
    {
        "https://app.face.local",
        "http://127.0.0.1:3000",
        "http://localhost:3000"
    };
}

public class AiConfig
{
    [JsonPropertyName("faceExecutionProviders")]
    public string[] FaceExecutionProviders { get; set; } = new[] 
    {
        "CUDAExecutionProvider", 
        "CPUExecutionProvider"
    };

    [JsonPropertyName("faceModelName")]
    public string FaceModelName { get; set; } = "buffalo_l";
}
