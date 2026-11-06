[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$TextFile,
    [ValidateRange(-5,5)][int]$Rate = 0,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
try {
    $resolvedText = (Resolve-Path -LiteralPath $TextFile).Path
    $speechText = [System.IO.File]::ReadAllText($resolvedText, [System.Text.Encoding]::UTF8)
    if ([string]::IsNullOrWhiteSpace($speechText)) { throw '朗读文字为空' }
    if ($speechText.Length -gt 3000) { throw '每次最多朗读 3000 字，请仅提交当前题目' }
    Add-Type -AssemblyName System.Speech
    $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $chineseVoice = $speaker.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'zh-*' } | Select-Object -First 1
        if (-not $chineseVoice) { throw '未找到中文语音，请在 Windows 语音设置安装中文语音包，或继续文字模拟' }
        $speaker.SelectVoice($chineseVoice.VoiceInfo.Name)
        $speaker.Rate = $Rate
        if (-not $CheckOnly) { $speaker.Speak($speechText) }
        @{ status = $(if ($CheckOnly) { 'ready' } else { 'spoken' }); voice = $chineseVoice.VoiceInfo.Name; characters = $speechText.Length } | ConvertTo-Json -Compress
    } finally { $speaker.Dispose() }
} catch {
    Write-Error ('【需要你操作】朗读未完成：' + $_.Exception.Message) -ErrorAction Continue
    exit 1
}
