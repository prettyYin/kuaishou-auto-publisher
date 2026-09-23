using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

class KuaishouAutoLauncher
{
    [STAThread]
    static void Main()
    {
        string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string python = FindPython(dir);
        if (python == null)
        {
            MessageBox.Show(
                "没有找到 Python 运行时。\n\n请确认免安装包完整（应包含 python 目录），或联系管理员。",
                "快手自动发布助手",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            return;
        }

        string log = Path.Combine(dir, "启动日志.txt");
        try
        {
            File.AppendAllText(log, "===== 启动 " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " =====\r\n");
        }
        catch { }

        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = python;
        info.Arguments = "-X utf8 -m app.main";
        info.WorkingDirectory = dir;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        info.RedirectStandardOutput = true;
        info.RedirectStandardError = true;
        info.EnvironmentVariables["KUAISHOU_AUTO_LAUNCHER"] = "1";
        info.EnvironmentVariables["KUAISHOU_AUTO_EXE"] = Path.Combine(dir, "启动工具.exe");

        try
        {
            using (Process process = new Process())
            {
                process.StartInfo = info;
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e)
                {
                    if (e.Data != null) AppendLine(log, e.Data);
                };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
                {
                    if (e.Data != null) AppendLine(log, e.Data);
                };
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
            }
        }
        catch (Exception exc)
        {
            AppendLine(log, "启动失败：" + exc.Message);
            MessageBox.Show(
                "启动失败，详细信息已写入：\n" + log,
                "快手自动发布助手",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
        }
    }

    static string FindPython(string dir)
    {
        string bundled = Path.Combine(dir, "python", "python.exe");
        if (File.Exists(bundled)) return bundled;

        string[] fixedPaths = new string[]
        {
            @"F:\MySofeware\dev_tools\Python\Python39\python.exe",
            @"C:\Python39\python.exe"
        };
        foreach (string item in fixedPaths)
        {
            if (File.Exists(item)) return item;
        }

        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string part in path.Split(';'))
        {
            if (part.Trim().Length == 0) continue;
            try
            {
                string candidate = Path.Combine(part.Trim(), "python.exe");
                if (File.Exists(candidate)) return candidate;
            }
            catch { }
        }
        return null;
    }

    static void AppendLine(string path, string line)
    {
        try
        {
            File.AppendAllText(path, line + "\r\n");
        }
        catch { }
    }
}
