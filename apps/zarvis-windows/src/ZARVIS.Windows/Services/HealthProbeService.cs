using System.Net.Http;
using System.Text.Json;

namespace ZARVIS.Windows.Services;

public sealed class HealthProbeService : IDisposable
{
    private readonly HttpClient _client = new()
    {
        Timeout = TimeSpan.FromSeconds(3)
    };

    public async Task<HealthResult> ProbeAsync(int port, CancellationToken cancellationToken = default)
    {
        try
        {
            using var response = await _client.GetAsync(
                $"http://127.0.0.1:{port}/healthz",
                cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                return new HealthResult(false, $"HTTP {(int)response.StatusCode}");
            }

            await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
            using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
            var root = document.RootElement;

            var status = root.TryGetProperty("status", out var statusValue)
                ? statusValue.GetString()
                : null;
            var localOnly = root.TryGetProperty("local_only", out var localValue) &&
                            localValue.ValueKind == JsonValueKind.True;

            return status == "ok" && localOnly
                ? new HealthResult(true, "Healthy and local-only")
                : new HealthResult(false, "Health response violated local-only invariants");
        }
        catch (Exception exception) when (
            exception is HttpRequestException or TaskCanceledException or JsonException)
        {
            return new HealthResult(false, exception.Message);
        }
    }

    public void Dispose() => _client.Dispose();
}

public sealed record HealthResult(bool Healthy, string Detail);
