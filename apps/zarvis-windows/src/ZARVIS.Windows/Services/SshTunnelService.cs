using System.Collections.Concurrent;
using System.Diagnostics;
using ZARVIS.Windows.Models;

namespace ZARVIS.Windows.Services;

public sealed class SshTunnelService : IAsyncDisposable
{
    private readonly ConcurrentQueue<string> _diagnostics = new();
    private Process? _process;

    public bool IsRunning => _process is { HasExited: false };

    public event EventHandler<string>? DiagnosticReceived;
    public event EventHandler<int>? TunnelExited;

    public async Task StartAsync(ClientSettings settings, CancellationToken cancellationToken = default)
    {
        InputValidator.Validate(settings);

        if (IsRunning)
        {
            return;
        }

        var sshPath = ResolveSshPath();
        var startInfo = CreateBaseStartInfo(sshPath, settings);
        startInfo.ArgumentList.Add("-N");
        startInfo.ArgumentList.Add("-T");
        startInfo.ArgumentList.Add("-L");
        startInfo.ArgumentList.Add($"{settings.LocalActionPort}:127.0.0.1:{settings.RemoteActionPort}");
        startInfo.ArgumentList.Add("-L");
        startInfo.ArgumentList.Add($"{settings.LocalProactivePort}:127.0.0.1:{settings.RemoteProactivePort}");
        startInfo.ArgumentList.Add($"{settings.SshUser}@{settings.ServerHost}");

        _process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
        _process.ErrorDataReceived += (_, args) =>
        {
            if (string.IsNullOrWhiteSpace(args.Data))
            {
                return;
            }

            _diagnostics.Enqueue(args.Data);
            DiagnosticReceived?.Invoke(this, args.Data);
        };
        _process.Exited += (_, _) => TunnelExited?.Invoke(this, _process?.ExitCode ?? -1);

        if (!_process.Start())
        {
            throw new InvalidOperationException("Windows OpenSSH could not be started.");
        }

        _process.BeginErrorReadLine();
        await Task.Delay(900, cancellationToken);

        if (_process.HasExited)
        {
            throw new InvalidOperationException(
                $"SSH tunnel exited with code {_process.ExitCode}: {RecentDiagnostics()}");
        }
    }

    public async Task<string> ReadOwnerTokenAsync(
        ClientSettings settings,
        CancellationToken cancellationToken = default)
    {
        InputValidator.Validate(settings);

        var startInfo = CreateBaseStartInfo(ResolveSshPath(), settings);
        startInfo.RedirectStandardOutput = true;
        startInfo.ArgumentList.Add($"{settings.SshUser}@{settings.ServerHost}");
        startInfo.ArgumentList.Add(
            "sed -n 's/^ZARVIS_LOCAL_OWNER_TOKEN=//p' ~/z-platform/.env.zarvis.local");

        using var process = new Process { StartInfo = startInfo };
        if (!process.Start())
        {
            throw new InvalidOperationException("SSH token command could not be started.");
        }

        var outputTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var errorTask = process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);

        var output = (await outputTask).Trim();
        var error = (await errorTask).Trim();

        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                $"Owner token retrieval failed with code {process.ExitCode}: {error}");
        }

        if (output.Length < 32 || output.Contains('\n') || output.Contains('\r'))
        {
            throw new InvalidOperationException("Server returned an invalid owner token.");
        }

        return output;
    }

    public async Task StopAsync()
    {
        var process = _process;
        _process = null;

        if (process is null)
        {
            return;
        }

        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
                await process.WaitForExitAsync();
            }
        }
        finally
        {
            process.Dispose();
        }
    }

    public async ValueTask DisposeAsync() => await StopAsync();

    private static ProcessStartInfo CreateBaseStartInfo(string sshPath, ClientSettings settings)
    {
        var info = new ProcessStartInfo
        {
            FileName = sshPath,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardError = true
        };

        info.ArgumentList.Add("-p");
        info.ArgumentList.Add(settings.SshPort.ToString());
        info.ArgumentList.Add("-o");
        info.ArgumentList.Add("BatchMode=yes");
        info.ArgumentList.Add("-o");
        info.ArgumentList.Add("ExitOnForwardFailure=yes");
        info.ArgumentList.Add("-o");
        info.ArgumentList.Add("ServerAliveInterval=30");
        info.ArgumentList.Add("-o");
        info.ArgumentList.Add("ServerAliveCountMax=3");
        info.ArgumentList.Add("-o");
        info.ArgumentList.Add("StrictHostKeyChecking=accept-new");

        if (!string.IsNullOrWhiteSpace(settings.PrivateKeyPath))
        {
            info.ArgumentList.Add("-i");
            info.ArgumentList.Add(Environment.ExpandEnvironmentVariables(settings.PrivateKeyPath));
        }

        return info;
    }

    private static string ResolveSshPath()
    {
        var systemSsh = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            "System32",
            "OpenSSH",
            "ssh.exe");

        return File.Exists(systemSsh) ? systemSsh : "ssh.exe";
    }

    private string RecentDiagnostics()
    {
        var items = _diagnostics.ToArray();
        return string.Join(" | ", items.TakeLast(5));
    }
}
