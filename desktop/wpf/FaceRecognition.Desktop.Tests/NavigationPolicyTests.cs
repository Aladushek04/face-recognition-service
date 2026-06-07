using Xunit;

namespace FaceRecognition.Desktop.Tests;

public class NavigationPolicyTests
{
    [Theory]
    [InlineData("https://google.com", true)]
    [InlineData("http://example.org", true)]
    [InlineData("file:///C:/Windows/System32/cmd.exe", false)]
    [InlineData("shell:AppsFolder", false)]
    [InlineData("ms-settings:display", false)]
    [InlineData("smb://server/share", false)]
    [InlineData("javascript:alert(1)", false)]
    [InlineData("about:blank", false)]
    [InlineData("data:text/html,<html></html>", false)]
    public void IsSafeExternalUri_BlocksUnsafeSchemes(string uri, bool expectedSafe)
    {
        // Act
        bool result = MainWindow.IsSafeExternalUri(uri);
        
        // Assert
        Assert.Equal(expectedSafe, result);
    }
}
