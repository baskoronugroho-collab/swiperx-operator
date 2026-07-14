param([int]$Port = 5599, [string]$Root = "app")
$ErrorActionPreference = "Stop"
$rootPath = (Resolve-Path $Root).Path
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
$listener.Start()
Write-Host "Serving $rootPath at http://localhost:$Port/"
$mime = @{ ".html"="text/html"; ".js"="application/javascript"; ".css"="text/css"; ".png"="image/png"; ".jpg"="image/jpeg"; ".svg"="image/svg+xml"; ".json"="application/json"; ".csv"="text/csv" }
while ($listener.IsListening) {
  try {
    $ctx = $listener.GetContext()
    $rel = [System.Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
    if ([string]::IsNullOrEmpty($rel)) { $rel = "index.html" }
    $full = Join-Path $rootPath $rel
    if (Test-Path $full -PathType Container) { $full = Join-Path $full "index.html" }
    if (Test-Path $full -PathType Leaf) {
      $bytes = [System.IO.File]::ReadAllBytes($full)
      $ext = [System.IO.Path]::GetExtension($full).ToLower()
      if ($mime.ContainsKey($ext)) { $ctx.Response.ContentType = $mime[$ext] }
      $ctx.Response.StatusCode = 200
      $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    } else {
      $ctx.Response.StatusCode = 404
      $nf = [System.Text.Encoding]::UTF8.GetBytes("Not found: $rel")
      $ctx.Response.OutputStream.Write($nf, 0, $nf.Length)
    }
    $ctx.Response.OutputStream.Close()
  } catch { }
}
