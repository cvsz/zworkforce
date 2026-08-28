using Xunit;
using ZARVIS.Windows.Models;
using ZARVIS.Windows.Services;

namespace ZARVIS.Windows.Tests;

public sealed class InputValidatorTests
{
    [Fact]
    public void AcceptsOwnerLocalDefaults()
    {
        var settings = new ClientSettings
        {
            ServerHost = "192.168.74.130",
            SshUser = "cvsz",
            SshPort = 22,
            LocalActionPort = 8098,
            LocalProactivePort = 8099
        };

        InputValidator.Validate(settings);
    }

    [Theory]
    [InlineData("host;calc.exe")]
    [InlineData("host name")]
    [InlineData("")]
    public void RejectsUnsafeHost(string value)
    {
        var settings = new ClientSettings { ServerHost = value };
        Assert.Throws<ArgumentException>(() => InputValidator.Validate(settings));
    }

    [Fact]
    public void RejectsDuplicateLocalPorts()
    {
        var settings = new ClientSettings
        {
            LocalActionPort = 8098,
            LocalProactivePort = 8098
        };

        Assert.Throws<ArgumentException>(() => InputValidator.Validate(settings));
    }
}
