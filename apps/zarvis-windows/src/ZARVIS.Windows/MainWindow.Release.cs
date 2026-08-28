using System.Windows;

namespace ZARVIS.Windows;

public partial class MainWindow
{
    private void OpenReleasePage_Click(object sender, RoutedEventArgs e) =>
        OpenBrowser("https://github.com/cvsz/z-platform/releases");
}
