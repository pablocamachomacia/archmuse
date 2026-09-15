// Escala de un monitor y captura de una ventana, para capturar el instalador a
// una escala concreta. Lo carga capturar.ps1 con Add-Type.
//
// Cambiar la escala usa DisplayConfigGetDeviceInfo/SetDeviceInfo con los tipos
// -3 y -4 (DPI_SCALE_GET/SET): no están documentados, son los que usa la propia
// Configuración de Windows. La escala se expresa relativa a la recomendada del
// monitor; por eso se lee antes la actual y se calcula el salto.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;

public static class Pantalla
{
    [StructLayout(LayoutKind.Sequential)] struct LUID { public uint Low; public int High; }

    [StructLayout(LayoutKind.Sequential)]
    struct CABECERA { public int type; public int size; public LUID adapterId; public uint id; }

    [StructLayout(LayoutKind.Sequential)]
    struct ESCALA_LEIDA { public CABECERA cab; public int minimo; public int actual; public int maximo; }

    [StructLayout(LayoutKind.Sequential)]
    struct ESCALA_NUEVA { public CABECERA cab; public int relativa; }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct NOMBRE_ORIGEN { public CABECERA cab; [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string gdi; }

    [StructLayout(LayoutKind.Explicit, Size = 72)]
    struct RUTA { [FieldOffset(0)] public LUID adaptador; [FieldOffset(8)] public uint origen; }

    [StructLayout(LayoutKind.Explicit, Size = 64)]
    struct MODO { [FieldOffset(0)] public int tipo; }

    [DllImport("user32.dll")] static extern int GetDisplayConfigBufferSizes(uint flags, out uint rutas, out uint modos);
    [DllImport("user32.dll")] static extern int QueryDisplayConfig(uint flags, ref uint nRutas, [Out] RUTA[] rutas, ref uint nModos, [Out] MODO[] modos, IntPtr topologia);
    [DllImport("user32.dll")] static extern int DisplayConfigGetDeviceInfo(ref NOMBRE_ORIGEN p);
    [DllImport("user32.dll")] static extern int DisplayConfigGetDeviceInfo(ref ESCALA_LEIDA p);
    [DllImport("user32.dll")] static extern int DisplayConfigSetDeviceInfo(ref ESCALA_NUEVA p);

    static readonly int[] ESCALAS = { 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500 };

    static bool Buscar(string gdi, out LUID adaptador, out uint origen)
    {
        uint nr, nm;
        GetDisplayConfigBufferSizes(2, out nr, out nm);
        var rutas = new RUTA[nr]; var modos = new MODO[nm];
        if (QueryDisplayConfig(2, ref nr, rutas, ref nm, modos, IntPtr.Zero) != 0) throw new Exception("QueryDisplayConfig ha fallado");
        for (int i = 0; i < nr; i++)
        {
            var n = new NOMBRE_ORIGEN();
            n.cab.type = 1; n.cab.size = Marshal.SizeOf(typeof(NOMBRE_ORIGEN));
            n.cab.adapterId = rutas[i].adaptador; n.cab.id = rutas[i].origen;
            if (DisplayConfigGetDeviceInfo(ref n) == 0 && string.Equals(n.gdi, gdi, StringComparison.OrdinalIgnoreCase))
            { adaptador = rutas[i].adaptador; origen = rutas[i].origen; return true; }
        }
        adaptador = new LUID(); origen = 0; return false;
    }

    // (mínima, actual, máxima) relativas a la recomendada.
    public static int[] LeerRelativa(string gdi)
    {
        LUID a; uint o;
        if (!Buscar(gdi, out a, out o)) throw new Exception("No encuentro el monitor " + gdi);
        var p = new ESCALA_LEIDA();
        p.cab.type = -3; p.cab.size = Marshal.SizeOf(typeof(ESCALA_LEIDA)); p.cab.adapterId = a; p.cab.id = o;
        int r = DisplayConfigGetDeviceInfo(ref p);
        if (r != 0) throw new Exception("DPI_SCALE_GET ha devuelto " + r);
        return new[] { p.minimo, p.actual, p.maximo };
    }

    // Pone el monitor a `porcentaje`, sabiendo que ahora está a `porcentajeActual`.
    public static void PonerEscala(string gdi, int porcentajeActual, int porcentaje)
    {
        var rel = LeerRelativa(gdi);
        int recomendada = Array.IndexOf(ESCALAS, porcentajeActual) - rel[1];
        int objetivo = Array.IndexOf(ESCALAS, porcentaje) - recomendada;
        if (objetivo < rel[0] || objetivo > rel[2])
            throw new Exception(string.Format("{0}% no está entre las escalas de ese monitor", porcentaje));
        LUID a; uint o; Buscar(gdi, out a, out o);
        var p = new ESCALA_NUEVA();
        p.cab.type = -4; p.cab.size = Marshal.SizeOf(typeof(ESCALA_NUEVA)); p.cab.adapterId = a; p.cab.id = o;
        p.relativa = objetivo;
        int r = DisplayConfigSetDeviceInfo(ref p);
        if (r != 0) throw new Exception("DPI_SCALE_SET ha devuelto " + r);
    }

    // --- Ventanas ------------------------------------------------------------

    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr padre, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, StringBuilder l);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr despues, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int l, t, r, b; }
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h, int attr, out RECT r, int size);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);

    static string Texto(IntPtr h)
    {
        var s = new StringBuilder(1024);
        SendMessage(h, 0x000D, (IntPtr)1024, s);   // WM_GETTEXT: también en controles de otro proceso
        return s.ToString();
    }

    public static IntPtr VentanaQueEmpieza(string titulo)
    {
        IntPtr hallada = IntPtr.Zero;
        EnumWindows((h, l) => {
            var s = new StringBuilder(512); GetWindowText(h, s, 512);
            if (IsWindowVisible(h) && s.ToString().StartsWith(titulo)) { hallada = h; return false; }
            return true;
        }, IntPtr.Zero);
        return hallada;
    }

    // El control hijo visible cuyo texto empieza por `texto`.
    public static IntPtr Hijo(IntPtr ventana, string texto)
    {
        IntPtr hallado = IntPtr.Zero;
        EnumChildWindows(ventana, (h, l) => {
            if (IsWindowVisible(h) && Texto(h).StartsWith(texto)) { hallado = h; return false; }
            return true;
        }, IntPtr.Zero);
        return hallado;
    }

    public static List<string> Textos(IntPtr ventana)
    {
        var res = new List<string>();
        EnumChildWindows(ventana, (h, l) => { if (IsWindowVisible(h)) { var t = Texto(h); if (t.Length > 0) res.Add(t); } return true; }, IntPtr.Zero);
        return res;
    }

    public static void Pulsar(IntPtr boton) { PostMessage(boton, 0x00F5, IntPtr.Zero, IntPtr.Zero); }  // BM_CLICK

    public static RECT Marco(IntPtr h)
    {
        RECT r;
        if (DwmGetWindowAttribute(h, 9, out r, Marshal.SizeOf(typeof(RECT))) != 0) GetWindowRect(h, out r);  // sin la sombra
        return r;
    }

    public static void Capturar(IntPtr h, string ruta)
    {
        SetForegroundWindow(h);
        System.Threading.Thread.Sleep(400);
        var r = Marco(h);
        using (var bmp = new Bitmap(r.r - r.l, r.b - r.t))
        using (var g = Graphics.FromImage(bmp))
        {
            g.CopyFromScreen(r.l, r.t, 0, 0, bmp.Size);
            bmp.Save(ruta, ImageFormat.Png);
        }
    }
}
