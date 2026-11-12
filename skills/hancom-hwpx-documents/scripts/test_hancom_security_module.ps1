param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'hancom_com_guard.ps1')

function Get-HancomPreflightProcesses {
    @(Get-Process -Name Hwp -ErrorAction SilentlyContinue | ForEach-Object {
        [pscustomobject]@{ Id = [int]$_.Id; StartTime = $_.StartTime }
    })
}

function Get-HancomPreflightIdentity([int]$ProcessId) {
    Get-Process -Id $ProcessId -ErrorAction Stop
}

function Get-HancomPreflightWindows($Hwp) {
    if (-not ('HancomPreflightNative' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class HancomPreflightNative {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
'@
    }
    $windows = $null
    try {
        $windows = $Hwp.XHwpWindows
        $count = [int]$windows.Count
        if ($count -lt 1) { throw 'No same-object window handle is available.' }
        for ($index = 0; $index -lt $count; $index++) {
            $window = $null
            try {
                $window = $windows.Item($index)
                $handle = [IntPtr]([long]$window.WindowHandle)
                [uint32]$windowProcessId = 0
                $threadId = [HancomPreflightNative]::GetWindowThreadProcessId($handle, [ref]$windowProcessId)
                if ($handle -eq [IntPtr]::Zero -or $threadId -eq 0 -or $windowProcessId -eq 0) {
                    throw 'Same-object window-to-process binding failed.'
                }
                [pscustomobject]@{ Handle = $handle.ToInt64(); ProcessId = [int]$windowProcessId }
            }
            finally {
                if ($null -ne $window -and [Runtime.InteropServices.Marshal]::IsComObject($window)) {
                    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($window)
                }
            }
        }
    }
    finally {
        if ($null -ne $windows -and [Runtime.InteropServices.Marshal]::IsComObject($windows)) {
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($windows)
        }
    }
}

function Get-HancomPreflightDocumentCount($Hwp) {
    $documents = $null
    try { $documents = $Hwp.XHwpDocuments; [int]$documents.Count }
    finally {
        if ($null -ne $documents -and [Runtime.InteropServices.Marshal]::IsComObject($documents)) {
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($documents)
        }
    }
}

function Release-HancomPreflightReference($Hwp) {
    if ($null -ne $Hwp -and [Runtime.InteropServices.Marshal]::IsComObject($Hwp)) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($Hwp)
    }
}

function Invoke-HancomSecurityPreflight {
    $hwp = $null
    $owned = $false
    $ownerId = 0
    $ownerStart = $null
    $windowKey = ''
    $operationFailure = $null
    $baseline = @(Get-HancomPreflightProcesses)
    $baselineIds = @($baseline | ForEach-Object { [int]$_.Id })
    try {
        # Registration precedes binding; no visibility or message-mode changes.
        $hwp = New-HancomGuardedObject
        Write-Output 'REGISTERED=True'
        $bindings = @(Get-HancomPreflightWindows -Hwp $hwp)
        $processIds = @($bindings | Select-Object -ExpandProperty ProcessId -Unique)
        if ($processIds.Count -ne 1) { throw 'Object windows do not bind to one process.' }
        $boundProcessId = [int]$processIds[0]
        $ownerProcess = Get-HancomPreflightIdentity -ProcessId $boundProcessId
        if ($boundProcessId -le 0 -or $ownerProcess.Id -ne $boundProcessId -or
            $ownerProcess.ProcessName -ne 'Hwp' -or $boundProcessId -in $baselineIds) {
            throw 'Unbound or pre-existing process; no file access or quit authorized.'
        }
        if ((Get-HancomPreflightDocumentCount -Hwp $hwp) -ne 1) {
            throw 'Initial document scope is not exclusive; preserve the unowned object.'
        }
        $ownerId = $boundProcessId
        $ownerStart = $ownerProcess.StartTime
        $windowKey = ($bindings | Sort-Object Handle | ForEach-Object { "$($_.Handle):$($_.ProcessId)" }) -join ','
        $owned = $true
        Write-Output "OWNERSHIP=BOUND PID=$ownerId START=$($ownerStart.ToUniversalTime().ToString('o')) WINDOWS=$windowKey"
    }
    catch {
        $operationFailure = $_.Exception.Message
        throw
    }
    finally {
        if ($null -ne $hwp) {
            $canQuit = $false
            try {
                if ($owned) {
                    $current = Get-HancomPreflightIdentity -ProcessId $ownerId
                    $currentBindings = @(Get-HancomPreflightWindows -Hwp $hwp)
                    $currentKey = ($currentBindings | Sort-Object Handle | ForEach-Object { "$($_.Handle):$($_.ProcessId)" }) -join ','
                    $canQuit = ($current.Id -eq $ownerId -and $current.ProcessName -eq 'Hwp' -and
                        $current.StartTime -eq $ownerStart -and $currentKey -eq $windowKey -and
                        (Get-HancomPreflightDocumentCount -Hwp $hwp) -eq 1)
                }
                if (-not $canQuit) { throw 'Same-object ownership/document scope is unverified at cleanup.' }
                Close-HancomGuardedObject -Hwp $hwp
                $hwp = $null
                # Close catches Quit errors; independently check exact process exit.
                $deadline = [DateTime]::UtcNow.AddSeconds(2)
                do {
                    $remaining = @(Get-HancomPreflightProcesses | Where-Object {
                        $_.Id -eq $ownerId -and $_.StartTime -eq $ownerStart
                    })
                    if ($remaining.Count) { Start-Sleep -Milliseconds 100 }
                } while ($remaining.Count -and [DateTime]::UtcNow -lt $deadline)
                if ($remaining.Count) { throw 'The bound process remains after scoped Quit.' }
                Write-Output 'CLEANUP=VERIFIED'
            }
            catch {
                if ($null -ne $hwp) { Release-HancomPreflightReference -Hwp $hwp; $hwp = $null }
                throw "CLEANUP=UNRESOLVED: $($_.Exception.Message) PREFLIGHT=$operationFailure"
            }
        }
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

# Dot-sourcing exposes functions for synthetic tests without launching Hancom.
if ($MyInvocation.InvocationName -ne '.') { Invoke-HancomSecurityPreflight }
