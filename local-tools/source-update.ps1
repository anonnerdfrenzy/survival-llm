# Git-only update logic. The entry point supplies the author's URL; tests use
# local repositories. No remote names are assumed and no commits are created.
function Invoke-SourceUpdate {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Source
    )
    function Read-Git([string[]]$Arguments) {
        $output = & git -C $Root @Arguments
        if ($LASTEXITCODE -ne 0) { throw ('Git failed: ' + ($Arguments -join ' ')) }
        return $output
    }

    $branch = Read-Git @('branch', '--show-current')
    if (-not $branch) { throw 'Detached HEAD: switch to your local branch before updating.' }
    foreach ($operation in @('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer')) {
        $state = Read-Git @('rev-parse', '--git-path', $operation)
        if (-not [IO.Path]::IsPathRooted($state)) { $state = Join-Path $Root $state }
        if (Test-Path -LiteralPath $state) { throw 'Finish the current Git operation before updating.' }
    }
    if (Read-Git @('status', '--porcelain=v1', '--untracked-files=no')) {
        throw 'Tracked files have local changes. Save them before updating.'
    }

    Read-Git @('fetch', '--no-tags', '--no-recurse-submodules', '--', $Source, 'main') | Out-Host
    # Capture the fetched commit so a concurrent fetch cannot change the merge target.
    $target = Read-Git @('rev-parse', '--verify', 'FETCH_HEAD^{commit}')
    $counts = (Read-Git @('rev-list', '--left-right', '--count', "HEAD...$target")) -split '\s+'
    $ahead = [int]$counts[0]
    $behind = [int]$counts[1]
    if ($behind -eq 0) {
        Write-Host "Already contains the author's main. Local commits preserved: $ahead."
        return
    }
    if ($ahead -gt 0) {
        throw "Histories diverged ($ahead local, $behind upstream commits). Branch and files are unchanged. Review git diff HEAD...$target, then merge $target manually on your feature branch. No reset, rebase or automatic commit was performed."
    }
    Read-Git @('merge', '--ff-only', $target) | Out-Host
    Write-Host 'Source updated by fast-forward. Rerun Setup.cmd if dependency requirements changed.'
}
