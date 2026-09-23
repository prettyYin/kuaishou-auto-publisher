# -*- coding: utf-8 -*-
$ErrorActionPreference = "Stop"

$source = "C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20"
$target = "E:\Codex Project"
$sourceGit = Join-Path $source ".git"

Write-Host "源目录: $source"
Write-Host "目标目录: $target"

if (!(Test-Path -LiteralPath $source)) {
    throw "找不到源目录：$source"
}
if (!(Test-Path -LiteralPath $target)) {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
}

Write-Host "正在复制工作区（保留 C 盘原目录作为备份）..."
& robocopy $source $target /E /XD "$sourceGit" /R:2 /W:1 /NFL /NDL /NP
if ($LASTEXITCODE -ge 8) {
    throw "robocopy 复制失败，退出码：$LASTEXITCODE"
}

Write-Host "正在迁移 Git 元数据..."
$targetGit = Join-Path $target ".git"
if (Test-Path -LiteralPath $targetGit) {
    Remove-Item -LiteralPath $targetGit -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $source "work\.gitdata") -Destination $targetGit -Recurse -Force

# 让 Git 在 E 盘根目录使用新的工作区
$gitConfig = Join-Path $targetGit "config"
$gitText = Get-Content -Raw -LiteralPath $gitConfig
$gitText = $gitText -replace "worktree\s*=.*", "worktree = E:/Codex Project"
Set-Content -LiteralPath $gitConfig -Value $gitText -Encoding ASCII

Write-Host "正在更新脚本里的 C 盘绝对路径..."
$textExtensions = @(".py", ".cmd", ".cs", ".bat")
$files = Get-ChildItem -LiteralPath $target -Recurse -File | Where-Object { $textExtensions -contains $_.Extension }
foreach ($file in $files) {
    $text = Get-Content -Raw -LiteralPath $file.FullName
    if ($text -like "*$source*") {
        $text.Replace($source, $target) | Set-Content -LiteralPath $file.FullName -Encoding UTF8
    }
}

Write-Host "正在把自动化浏览器副本目录改到 E 盘..."
$configPath = Join-Path $target "outputs\快手自动发布助手\config\config.json"
if (Test-Path -LiteralPath $configPath) {
    $config = Get-Content -Raw -Encoding UTF8 -LiteralPath $configPath | ConvertFrom-Json
    $config.automation_data_dir = "E:\Codex Project\KuaishouAuto"
    $config | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $configPath -Encoding UTF8
}

git config --global --add safe.directory "E:/Codex Project"

Write-Host ""
Write-Host "迁移完成。"
Write-Host "新工作区：E:\Codex Project"
Write-Host "C 盘原目录暂时保留作为备份。"
Write-Host ""
Write-Host "下一步：在 Codex 中把工作区切换为 E:\Codex Project，然后运行："
Write-Host "  cd `"E:\Codex Project\outputs\快手自动发布助手`""
Write-Host "  python -X utf8 -m app.selftest"
Write-Host ""
Write-Host "Chrome 程序本身和 Chrome 原始登录目录仍在 C 盘，这是必须保留的。"
