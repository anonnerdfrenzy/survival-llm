# Text read off a scanned PDF or a photo with Windows' own OCR engine (Windows 10/11), for myfiles.py.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File winocr.ps1 <file>
# Prints UTF-8 text; the pages of a PDF are separated by a blank line. Exit 1 on failure.
param([Parameter(Mandatory=$true)][string]$Path)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[void][Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
[void][Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
[void][Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime]
[void][Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
[void][Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]

$methods = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 }
$asTaskOp = ($methods | Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$asTaskAction = ($methods | Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
function Await($op, $type) {
    $task = $asTaskOp.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}
function AwaitAction($op) {
    $task = $asTaskAction.Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
}

$engine = $null
foreach ($tag in @("nl-NL", "en-US", "en-GB")) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($tag))
    if ($null -ne $engine) { break }
}
if ($null -eq $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($null -eq $engine) { [Console]::Error.WriteLine("No OCR language is installed in Windows."); exit 1 }

function Recognize($stream) {
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $bitmap.Dispose()
    ($result.Lines | ForEach-Object { $_.Text }) -join "`n"
}

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $Path).Path)) ([Windows.Storage.StorageFile])
$out = New-Object System.Text.StringBuilder
if ([IO.Path]::GetExtension($Path).ToLower() -eq ".pdf") {
    $doc = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
    for ($i = 0; $i -lt $doc.PageCount; $i++) {
        $page = $doc.GetPage($i)
        $options = New-Object Windows.Data.Pdf.PdfPageRenderOptions
        $scale = 1700 / [Math]::Max($page.Size.Width, 1)   # about 200 dpi on an A4 page
        $options.DestinationWidth = [uint32]([Math]::Min(4000, $page.Size.Width * $scale))
        $options.DestinationHeight = [uint32]([Math]::Min(4000, $page.Size.Height * $scale))
        $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
        AwaitAction ($page.RenderToStreamAsync($stream, $options))
        $stream.Seek(0)
        $text = Recognize $stream
        $stream.Dispose(); $page.Dispose()
        [void]$out.Append($text).Append("`n`n")
    }
} else {
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    [void]$out.Append((Recognize $stream))
    $stream.Dispose()
}
[Console]::Out.Write($out.ToString())
exit 0
