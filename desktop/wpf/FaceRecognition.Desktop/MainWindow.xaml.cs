using System;
using System.ComponentModel;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using FaceRecognition.Desktop.Services;
using Microsoft.Web.WebView2.Core;

namespace FaceRecognition.Desktop;

public partial class MainWindow : Window
{
    private BackendProcessManager? _backend;

    public MainWindow()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Closing += OnClosing;
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            _backend = new BackendProcessManager();
            var runtime = await _backend.StartAsync();
            await InitializeWebViewAsync(runtime.ApiBaseUrl);
        }
        catch (Exception ex)
        {
            ShowStartupError(ex);
        }
    }

    private async Task InitializeWebViewAsync(string apiBaseUrl)
    {
        var userDataFolder = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "FaceRecognitionService",
            "WebView2"
        );

        var environment = await CoreWebView2Environment.CreateAsync(
            browserExecutableFolder: null,
            userDataFolder: userDataFolder
        );

        await MainWebView.EnsureCoreWebView2Async(environment);
#if DEBUG
        MainWebView.CoreWebView2.Settings.AreDevToolsEnabled = true;
#else
        MainWebView.CoreWebView2.Settings.AreDevToolsEnabled = Environment.GetEnvironmentVariable("FACE_DESKTOP_DEVTOOLS") == "true";
#endif

        MainWebView.CoreWebView2.NavigationStarting += (_, args) =>
        {
            HandleExternalNavigation(args.Uri, () => args.Cancel = true);
        };

        MainWebView.CoreWebView2.NewWindowRequested += (_, args) =>
        {
            HandleExternalNavigation(args.Uri, () => args.Handled = true);
        };

        var frontendDist = AppPaths.FrontendDistPath;

        if (Directory.Exists(frontendDist) && File.Exists(Path.Combine(frontendDist, "index.html")))
        {
            MainWebView.CoreWebView2.SetVirtualHostNameToFolderMapping(
                "app.face.local",
                frontendDist,
                CoreWebView2HostResourceAccessKind.Allow
            );

            await MainWebView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync($@"
                window.__FACE_SERVICE_CONFIG__ = {{
                    apiBaseUrl: '{apiBaseUrl}'
                }};
            ");

            MainWebView.Source = new Uri($"https://app.face.local/index.html");
        }
        else
        {
            MainWebView.Source = new Uri($"http://127.0.0.1:3000?apiBaseUrl={Uri.EscapeDataString(apiBaseUrl)}");
        }

        MainWebView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
    }

    private void HandleExternalNavigation(string uriString, Action cancelAction)
    {
        if (string.IsNullOrWhiteSpace(uriString))
        {
            cancelAction();
            return;
        }

        if (uriString.StartsWith("https://app.face.local", StringComparison.OrdinalIgnoreCase) ||
            uriString.StartsWith("http://127.0.0.1", StringComparison.OrdinalIgnoreCase) ||
            uriString.StartsWith("http://localhost", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        cancelAction();

        if (IsSafeExternalUri(uriString))
        {
            try 
            {
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                {
                    FileName = uriString,
                    UseShellExecute = true
                });
            } 
            catch { }
        }
    }

    internal static bool IsSafeExternalUri(string uriString)
    {
        if (Uri.TryCreate(uriString, UriKind.Absolute, out var uri))
        {
            return uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps;
        }
        return false;
    }

    private void AppendLog(string message)
    {
        try
        {
            var logPath = Path.Combine(AppPaths.LogsPath, "app.log");
            Directory.CreateDirectory(AppPaths.LogsPath);
            File.AppendAllText(logPath, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {message}{Environment.NewLine}");
        }
        catch { }
    }

    private void OnWebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        var source = e.Source;
        if (!source.StartsWith("https://app.face.local") && 
            !source.StartsWith("http://127.0.0.1:3000") && 
            !source.StartsWith("http://localhost:3000"))
        {
            AppendLog($"[WebViewBridge] Rejected origin: {source}");
            return;
        }

        try
        {
            var json = e.WebMessageAsJson;
            if (string.IsNullOrEmpty(json)) return;

            AppendLog($"[WebViewBridge] WebMessageReceived: {json}");

            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;
            
            if (!root.TryGetProperty("action", out var actionElement)) return;
            var action = actionElement.GetString();

            if (action == "closeApp")
            {
                AppendLog("[WebViewBridge] closeApp requested");
                Application.Current.Dispatcher.Invoke(() => {
                    Close();
                });
            }
            else if (action == "selectFolder")
            {
                if (!root.TryGetProperty("requestId", out var reqIdElement) ||
                    !root.TryGetProperty("field", out var fieldElement)) return;
                
                var requestId = reqIdElement.GetString();
                var field = fieldElement.GetString();
                
                var validFields = new[] { "baseDir", "actorsDir", "modelsDir", "faissIndexDir", "videosDir" };
                if (Array.IndexOf(validFields, field) == -1)
                {
                    AppendLog($"[WebViewBridge] selectFolder rejected invalid field: {field}");
                    return;
                }

                string initialDirectory = string.Empty;
                if (root.TryGetProperty("currentPath", out var pathElement))
                {
                    initialDirectory = pathElement.GetString() ?? string.Empty;
                }

                AppendLog($"[WebViewBridge] selectFolder requested: field={field} currentPath={initialDirectory}");

                Application.Current.Dispatcher.Invoke(() => {
                    var dialog = new Microsoft.Win32.OpenFolderDialog
                    {
                        Title = "Select Folder",
                        InitialDirectory = Directory.Exists(initialDirectory) ? initialDirectory : string.Empty
                    };

                    bool? result = dialog.ShowDialog(this);
                    
                    if (result == true)
                    {
                        AppendLog($"[WebViewBridge] selectFolder result: {dialog.FolderName}");
                    }
                    else
                    {
                        AppendLog("[WebViewBridge] selectFolder cancelled");
                    }

                    var response = new
                    {
                        action = "selectFolderResult",
                        requestId = requestId,
                        field = field,
                        path = result == true ? dialog.FolderName : null,
                        cancelled = result != true
                    };

                    var responseJson = System.Text.Json.JsonSerializer.Serialize(response);
                    MainWebView.CoreWebView2.PostWebMessageAsJson(responseJson);
                });
            }
            else
            {
                AppendLog($"[WebViewBridge] Rejected action: {action}");
            }
        }
        catch (Exception ex)
        {
            AppendLog($"[WebViewBridge] Error: {ex.Message}");
        }
    }

    private void OnClosing(object? sender, CancelEventArgs e)
    {
        _backend?.Stop();
    }

    private void ShowStartupError(Exception ex)
    {
        MessageBox.Show(
            $"Face Recognition Service failed to start.\n\nReason: {ex.Message}\n\nLogs path: {AppPaths.LogsPath}",
            "Startup Error",
            MessageBoxButton.OK,
            MessageBoxImage.Error
        );
        Application.Current.Shutdown();
    }
}
