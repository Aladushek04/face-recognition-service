using System.Diagnostics;

namespace FaceRecognition.Desktop.Models;

public sealed class BackendRuntimeInfo
{
    public required int Port { get; init; }
    public required string ApiBaseUrl { get; init; }
    public required Process Process { get; init; }
}
