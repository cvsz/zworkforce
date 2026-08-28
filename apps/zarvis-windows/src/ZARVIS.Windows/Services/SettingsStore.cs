using System.Text.Json;
using ZARVIS.Windows.Models;

namespace ZARVIS.Windows.Services;

public sealed class SettingsStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    private readonly string _directory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "ZARVIS");

    public string SettingsPath => Path.Combine(_directory, "settings.json");

    public async Task<ClientSettings> LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(SettingsPath))
        {
            return new ClientSettings();
        }

        await using var stream = File.OpenRead(SettingsPath);
        return await JsonSerializer.DeserializeAsync<ClientSettings>(
                   stream,
                   JsonOptions,
                   cancellationToken)
               ?? new ClientSettings();
    }

    public async Task SaveAsync(ClientSettings settings, CancellationToken cancellationToken = default)
    {
        InputValidator.Validate(settings);
        Directory.CreateDirectory(_directory);

        var temporary = $"{SettingsPath}.tmp";
        await using (var stream = new FileStream(
                         temporary,
                         FileMode.Create,
                         FileAccess.Write,
                         FileShare.None,
                         4096,
                         FileOptions.WriteThrough))
        {
            await JsonSerializer.SerializeAsync(stream, settings, JsonOptions, cancellationToken);
            await stream.FlushAsync(cancellationToken);
        }

        File.Move(temporary, SettingsPath, true);
    }
}
