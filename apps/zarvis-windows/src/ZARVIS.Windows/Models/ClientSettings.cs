namespace ZARVIS.Windows.Models;

public sealed record ClientSettings
{
    public string ServerHost { get; init; } = "192.168.74.130";
    public string SshUser { get; init; } = "cvsz";
    public int SshPort { get; init; } = 22;
    public string PrivateKeyPath { get; init; } = string.Empty;
    public int LocalActionPort { get; init; } = 8098;
    public int LocalProactivePort { get; init; } = 8099;
    public int RemoteActionPort { get; init; } = 8098;
    public int RemoteProactivePort { get; init; } = 8099;
    public bool AutoConnect { get; init; }
}
