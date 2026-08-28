using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;
using ZARVIS.Windows.Models;
using ZARVIS.Windows.Services;

namespace ZARVIS.Windows;

public partial class MainWindow : Window
{
    private readonly SettingsStore _settingsStore = new();
    private readonly SshTunnelService _tunnel = new();
    private readonly HealthProbeService _health = new();
    private CancellationTokenSource? _monitorCancellation;
    private ClientSettings _settings = new();

    public MainWindow()
    {
        InitializeComponent();
        Loaded += MainWindow_Loaded;
        Closing += MainWindow_Closing;
        _tunnel.DiagnosticReceived += (_, message) =>
            Dispatcher.Invoke(() => AppendLog($"ssh: {message}"));
        _tunnel.TunnelExited += (_, exitCode) =>
            Dispatcher.Invoke(() =>
            {
                AppendLog($"SSH tunnel exited with code {exitCode}.");
                SetConnected(false);
            });
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        try
        {
            _settings = await _settingsStore.LoadAsync();
            Populate(_settings);
            AppendLog($"Settings: {_settingsStore.SettingsPath}");
            AppendLog("Owner Token is not stored by this application.");

            if (_settings.AutoConnect)
            {
                await ConnectAsync();
            }
        }
        catch (Exception exception)
        {
            ShowError(exception);
        }
    }

    private async void MainWindow_Closing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        _monitorCancellation?.Cancel();
        await _tunnel.StopAsync();
        _health.Dispose();
    }

    private async void Connect_Click(object sender, RoutedEventArgs e) => await ConnectAsync();

    private async Task ConnectAsync()
    {
        try
        {
            SetBusy(true);
            _settings = ReadSettings();
            await _settingsStore.SaveAsync(_settings);
            AppendLog($"Connecting to {_settings.SshUser}@{_settings.ServerHost}…");
            await _tunnel.StartAsync(_settings);
            await WaitForHealthAsync(_settings);
            SetConnected(true);
            StartHealthMonitor();
            AppendLog("Secure tunnel and both local-only health endpoints are ready.");
        }
        catch (Exception exception)
        {
            await _tunnel.StopAsync();
            SetConnected(false);
            ShowError(exception);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void Disconnect_Click(object sender, RoutedEventArgs e)
    {
        _monitorCancellation?.Cancel();
        await _tunnel.StopAsync();
        SetConnected(false);
        AppendLog("Secure tunnel stopped.");
    }

    private async void Save_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            _settings = ReadSettings();
            await _settingsStore.SaveAsync(_settings);
            AppendLog("Settings saved.");
        }
        catch (Exception exception)
        {
            ShowError(exception);
        }
    }

    private void BrowseKey_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "Select SSH private key",
            Filter = "SSH private keys|id_*;*.pem;*.key|All files|*.*",
            CheckFileExists = true
        };

        if (dialog.ShowDialog(this) == true)
        {
            PrivateKeyBox.Text = dialog.FileName;
        }
    }

    private void OpenAction_Click(object sender, RoutedEventArgs e) =>
        OpenBrowser($"http://127.0.0.1:{_settings.LocalActionPort}");

    private void OpenProactive_Click(object sender, RoutedEventArgs e) =>
        OpenBrowser($"http://127.0.0.1:{_settings.LocalProactivePort}");

    private static void OpenBrowser(string url) =>
        Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });

    private static void OpenReleases_Click(object sender, RoutedEventArgs e) =>
        OpenBrowser("https://github.com/cvsz/z-platform/releases");

    private async void CopyToken_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            CopyTokenButton.IsEnabled = false;
            AppendLog("Retrieving Owner Token through one-shot encrypted SSH…");
            var token = await _tunnel.ReadOwnerTokenAsync(_settings);
            Clipboard.SetText(token);
            AppendLog("Owner Token copied. Clipboard will be cleared after 60 seconds.");

            _ = ClearClipboardLaterAsync(token);
        }
        catch (Exception exception)
        {
            ShowError(exception);
        }
        finally
        {
            CopyTokenButton.IsEnabled = _tunnel.IsRunning;
        }
    }

    private async Task ClearClipboardLaterAsync(string token)
    {
        await Task.Delay(TimeSpan.FromSeconds(60));
        await Dispatcher.InvokeAsync(() =>
        {
            try
            {
                if (Clipboard.ContainsText() && Clipboard.GetText() == token)
                {
                    Clipboard.Clear();
                    AppendLog("Owner Token removed from clipboard.");
                }
            }
            catch
            {
                AppendLog("Clipboard could not be cleared automatically.");
            }
        });
    }

    private async Task WaitForHealthAsync(ClientSettings settings)
    {
        for (var attempt = 1; attempt <= 30; attempt++)
        {
            var action = await _health.ProbeAsync(settings.LocalActionPort);
            var proactive = await _health.ProbeAsync(settings.LocalProactivePort);

            if (action.Healthy && proactive.Healthy)
            {
                return;
            }

            if (attempt == 30)
            {
                throw new InvalidOperationException(
                    $"Tunnel started but health verification failed. Action={action.Detail}; Proactive={proactive.Detail}");
            }

            await Task.Delay(500);
        }
    }

    private void StartHealthMonitor()
    {
        _monitorCancellation?.Cancel();
        _monitorCancellation = new CancellationTokenSource();
        _ = MonitorHealthAsync(_monitorCancellation.Token);
    }

    private async Task MonitorHealthAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested && _tunnel.IsRunning)
        {
            try
            {
                await Task.Delay(TimeSpan.FromSeconds(15), cancellationToken);
                var action = await _health.ProbeAsync(_settings.LocalActionPort, cancellationToken);
                var proactive = await _health.ProbeAsync(_settings.LocalProactivePort, cancellationToken);

                if (!action.Healthy || !proactive.Healthy)
                {
                    await Dispatcher.InvokeAsync(() =>
                    {
                        StatusText.Text = "Degraded";
                        StatusDot.Fill = new SolidColorBrush(Color.FromRgb(231, 177, 62));
                        AppendLog($"Health degraded. Action={action.Detail}; Proactive={proactive.Detail}");
                    });
                }
                else
                {
                    await Dispatcher.InvokeAsync(() => SetConnected(true));
                }
            }
            catch (OperationCanceledException)
            {
                return;
            }
        }
    }

    private ClientSettings ReadSettings()
    {
        return new ClientSettings
        {
            ServerHost = ServerHostBox.Text.Trim(),
            SshUser = SshUserBox.Text.Trim(),
            SshPort = ParsePort(SshPortBox.Text, "SSH port"),
            PrivateKeyPath = PrivateKeyBox.Text.Trim(),
            LocalActionPort = ParsePort(ActionPortBox.Text, "Action port"),
            LocalProactivePort = ParsePort(ProactivePortBox.Text, "Proactive port"),
            RemoteActionPort = 8098,
            RemoteProactivePort = 8099,
            AutoConnect = AutoConnectCheck.IsChecked == true
        };
    }

    private static int ParsePort(string text, string label)
    {
        if (!int.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out var value))
        {
            throw new ArgumentException($"{label} must be an integer.");
        }

        return value;
    }

    private void Populate(ClientSettings settings)
    {
        ServerHostBox.Text = settings.ServerHost;
        SshUserBox.Text = settings.SshUser;
        SshPortBox.Text = settings.SshPort.ToString(CultureInfo.InvariantCulture);
        PrivateKeyBox.Text = settings.PrivateKeyPath;
        ActionPortBox.Text = settings.LocalActionPort.ToString(CultureInfo.InvariantCulture);
        ProactivePortBox.Text = settings.LocalProactivePort.ToString(CultureInfo.InvariantCulture);
        AutoConnectCheck.IsChecked = settings.AutoConnect;
    }

    private void SetBusy(bool busy)
    {
        ConnectButton.IsEnabled = !busy && !_tunnel.IsRunning;
        DisconnectButton.IsEnabled = !busy && _tunnel.IsRunning;
    }

    private void SetConnected(bool connected)
    {
        StatusText.Text = connected ? "Connected" : "Disconnected";
        StatusDot.Fill = new SolidColorBrush(
            connected ? Color.FromRgb(67, 217, 195) : Color.FromRgb(224, 90, 103));
        ConnectButton.IsEnabled = !connected;
        DisconnectButton.IsEnabled = connected;
        OpenActionButton.IsEnabled = connected;
        OpenProactiveButton.IsEnabled = connected;
        CopyTokenButton.IsEnabled = connected;
    }

    private void AppendLog(string message)
    {
        LogBox.AppendText($"[{DateTimeOffset.Now:HH:mm:ss}] {message}{Environment.NewLine}");
        LogBox.ScrollToEnd();
    }

    private void ShowError(Exception exception)
    {
        AppendLog($"ERROR: {exception.Message}");
        MessageBox.Show(this, exception.Message, "Z.A.R.V.I.S.", MessageBoxButton.OK, MessageBoxImage.Error);
    }
}
