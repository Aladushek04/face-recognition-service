using System.Net;
using System.Net.Sockets;

namespace FaceRecognition.Desktop.Services;

public static class PortFinder
{
    public static int FindFreeTcpPort()
    {
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        try
        {
            return ((IPEndPoint)listener.LocalEndpoint).Port;
        }
        finally
        {
            listener.Stop();
        }
    }
}
