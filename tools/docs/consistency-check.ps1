# consistency-check.ps1
# OmniMemora 文档一致性本地检查脚本
# 用法: pwsh tools/docs/consistency-check.ps1
#
# 检查项（与 CI 同规则）：
#   1. doc_id 唯一性
#   2. depends_on 引用存在性
#   3. deprecated 文档有 supersedes
#   4. 必填元数据字段存在性
#   5. 链接完整性

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $RepoRoot) { $RepoRoot = "." }

$MarkdownFiles = Get-ChildItem -Path $RepoRoot -Recurse -Include "*.md" |
    Where-Object { $_.FullName -notmatch "\.git\\|\.pytest_cache\\|node_modules\\" }

Write-Host "=== OmniMemora 文档一致性检查 ===" -ForegroundColor Cyan
Write-Host "扫描 $($MarkdownFiles.Count) 个 Markdown 文件...`n" -ForegroundColor Gray

# ---- 1. 收集所有 doc_id ----
$DocIdPattern = [regex]"^doc_id:\s*(\S+)\s*$"
$IdMap = @{}  # doc_id -> file list
foreach ($f in $MarkdownFiles) {
    $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    $match = $DocIdPattern.Match($content)
    if ($match.Success) {
        $id = $match.Groups[1].Value
        if (-not $IdMap.ContainsKey($id)) { $IdMap[$id] = @() }
        $IdMap[$id] += $f.FullName
    }
}

$dupIds = $IdMap.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 }
if ($dupIds) {
    Write-Host "[FAIL] 重复 doc_id:" -ForegroundColor Red
    foreach ($d in $dupIds) {
        Write-Host "  $($d.Key) -> $($d.Value -join ', ')"
    }
} else {
    Write-Host "[PASS] doc_id 唯一性: $($IdMap.Count) 个文档全部唯一" -ForegroundColor Green
}

# ---- 2. depends_on 引用检查 ----
$DependsPattern = [regex]"^depends_on:\s*\[(.*?)\]\s*$" -replace "\\|\\|", ""
$StatusPattern  = [regex]"^status:\s*(\S+)\s*$"
$SupersedesPattern = [regex]"^supersedes:\s*\[(.*?)\]\s*$"

$brokenDeps = @()
$orphanDeps = @()
foreach ($f in $MarkdownFiles) {
    $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    # Extract depends_on
    $depsMatch = [regex]::Matches($content, "(?m)^depends_on:\s*\[(.*?)\]\s*$")
    if ($depsMatch.Success) {
        $raw = $depsMatch[0].Groups[1].Value
        $deps = $raw -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
        foreach ($dep in $deps) {
            if (-not $IdMap.ContainsKey($dep)) {
                $orphanDeps += "  $($f.Name) -> depends_on:'$dep' (不存在)"
            }
        }
    }
    # Check deprecated has supersedes
    $statusMatch = $StatusPattern.Match($content)
    if ($statusMatch.Success -and $statusMatch.Groups[1].Value -eq "deprecated") {
        $supersedesMatch = $SupersedesPattern.Match($content)
        $supersedesVal = if ($supersedesMatch.Success) { $supersedesMatch.Groups[1].Value.Trim() } else { "" }
        if (-not $supersedesVal) {
            $brokenDeps += "  $($f.Name) 是 deprecated 但无 supersedes"
        }
    }
}

if ($orphanDeps) {
    Write-Host "[FAIL] 失效的 depends_on 引用:" -ForegroundColor Red
    $orphanDeps | ForEach-Object { Write-Host $_ }
} else {
    Write-Host "[PASS] depends_on 引用完整性" -ForegroundColor Green
}

if ($brokenDeps) {
    Write-Host "[FAIL] deprecated 文档缺少 supersedes:" -ForegroundColor Red
    $brokenDeps | ForEach-Object { Write-Host $_ }
} else {
    Write-Host "[PASS] deprecated 文档均有 supersedes" -ForegroundColor Green
}

# ---- 3. 必填元数据字段 ----
$RequiredFields = @("doc_id", "title", "status", "version")
$missingFields = @()
foreach ($f in $MarkdownFiles) {
    $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    if (-not $content.StartsWith("---")) { continue }
    $frontmatterEnd = $content.IndexOf("---", 3)
    if ($frontmatterEnd -eq -1) { continue }
    $frontmatter = $content.Substring(0, $frontmatterEnd)
    foreach ($field in $RequiredFields) {
        if (-not ($frontmatter -match [regex]"^$field :")) {
            $missingFields += "  $($f.Name) 缺少 '$field'"
        }
    }
}

if ($missingFields) {
    Write-Host "[FAIL] 文档缺少必填元数据字段:" -ForegroundColor Red
    $missingFields | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
    if ($missingFields.Count -gt 20) { Write-Host "  ... 还有 $($missingFields.Count - 20) 个" -ForegroundColor Gray }
} else {
    Write-Host "[PASS] 所有文档包含必填元数据字段" -ForegroundColor Green
}

# ---- 4. 链接完整性 ----
$LinkPattern = [regex]'\[([^\]]+)\]\(([^\)]+)\)'
$brokenLinks = @()
foreach ($f in $MarkdownFiles) {
    $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    $fdir = Split-Path -Parent $f.FullName
    foreach ($m in $LinkPattern.Matches($content)) {
        $link = $m.Groups[2].Value
        if ($link -match "^(http|https|mailto|#):") { continue }
        $target = Join-Path $fdir $link
        if (-not (Test-Path $target)) {
            $brokenLinks += "  $($f.Name): [$($m.Groups[1].Value)]($link)"
        }
    }
}

if ($brokenLinks) {
    Write-Host "[FAIL] 失效的 Markdown 链接:" -ForegroundColor Red
    $brokenLinks | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
    if ($brokenLinks.Count -gt 20) { Write-Host "  ... 还有 $($brokenLinks.Count - 20) 个" -ForegroundColor Gray }
} else {
    Write-Host "[PASS] 所有 Markdown 链接有效" -ForegroundColor Green
}

Write-Host "`n=== 检查完成 ===" -ForegroundColor Cyan
