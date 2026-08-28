using System.Net;
using System.Text.RegularExpressions;
using ZARVIS.Windows.Models;

namespace ZARVIS.Windows.Services;

public static partial class InputValidator
{
    [GeneratedRegex(@"^[A-Za-z0-9._-]{1,64}$", RegexOptions.CultureInvariant)]
    private static partial Regex SafeIdentifier();

    [GeneratedRegex(@"^[A-Za-z0-9._:-]{1,255}$", RegexOptions.CultureInvariant)]
    private static partial Regex SafeHost();

    public static void Validate(ClientSettings settings)
    {
        if (string.IsNullOrWhiteSpace(settings.ServerHost) ||
            (!SafeHost().IsMatch(settings.ServerHost) &&
             !IPAddress.TryParse(settings.ServerHost, out _)))
        {
            throw new ArgumentException("Server host contains unsupported characters.");
        }

        if (string.IsNullOrWhiteSpace(settings.SshUser) ||
            !SafeIdentifier().IsMatch(settings.SshUser))
        {
            throw new ArgumentException("SSH user contains unsupported characters.");
        }

        ValidatePort(settings.SshPort, nameof(settings.SshPort));
        ValidatePort(settings.LocalActionPort, nameof(settings.LocalActionPort));
        ValidatePort(settings.LocalProactivePort, nameof(settings.LocalProactivePort));
        ValidatePort(settings.RemoteActionPort, nameof(settings.RemoteActionPort));
        ValidatePort(settings.RemoteProactivePort, nameof(settings.RemoteProactivePort));

        if (settings.LocalActionPort == settings.LocalProactivePort)
        {
            throw new ArgumentException("Action and Proactive local ports must differ.");
        }

        if (!string.IsNullOrWhiteSpace(settings.PrivateKeyPath) &&
            !File.Exists(Environment.ExpandEnvironmentVariables(settings.PrivateKeyPath)))
        {
            throw new FileNotFoundException("SSH private key was not found.", settings.PrivateKeyPath);
        }
    }

    private static void ValidatePort(int value, string name)
    {
        if (value is < 1 or > 65535)
        {
            throw new ArgumentOutOfRangeException(name, "Port must be between 1 and 65535.");
        }
    }
}
