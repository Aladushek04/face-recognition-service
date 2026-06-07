using Xunit;
using FaceRecognition.Desktop.Services;
using FaceRecognition.Desktop.Models;
using System.Diagnostics;
using System.Text.Json;

namespace FaceRecognition.Desktop.Tests;

public class BackendProcessManagerTests
{
    [Fact]
    public void ConfigureEnvironment_SetsExpectedVariables()
    {
        // Arrange
        var manager = new BackendProcessManager();
        var psi = new ProcessStartInfo();
        var config = new DesktopConfig();
        int port = 8080;
        
        // Act
        manager.ConfigureEnvironment(psi, config, port);
        
        // Assert
        Assert.Equal("127.0.0.1", psi.Environment["HOST"]);
        Assert.Equal("8080", psi.Environment["PORT"]);
        Assert.Equal("true", psi.Environment["DESKTOP_MODE"]);
        Assert.Equal("utf-8", psi.Environment["PYTHONIOENCODING"]);
        
        Assert.Equal(AppPaths.ConfigPath, psi.Environment["CONFIG_PATH"]);
        Assert.Equal(config.Runtime.BaseDir, psi.Environment["BASE_DIR"]);
        Assert.Equal(config.Runtime.JobsDir, psi.Environment["JOBS_DIR"]);
        Assert.Equal(config.Runtime.LogsDir, psi.Environment["LOGS_DIR"]);
        
        Assert.Equal(JsonSerializer.Serialize(config.Backend.CorsOrigins), psi.Environment["CORS_ORIGINS"]);
    }
}
