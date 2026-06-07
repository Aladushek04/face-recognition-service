using Xunit;
using FaceRecognition.Desktop.Services;
using FaceRecognition.Desktop.Models;
using System.IO;

namespace FaceRecognition.Desktop.Tests;

public class DesktopConfigLoaderTests
{
    [Fact]
    public void ValidateAndFallbackPaths_UsesLocalJobsAndLogsDirs()
    {
        // Arrange
        var config = new DesktopConfig();
        
        // Act
        DesktopConfigLoader.ValidateAndFallbackPaths(config);
        
        // Assert
        Assert.NotNull(config.Runtime);
        Assert.Equal(AppPaths.LocalJobsDir, config.Runtime.JobsDir);
        Assert.Equal(AppPaths.LogsPath, config.Runtime.LogsDir);
    }
}
