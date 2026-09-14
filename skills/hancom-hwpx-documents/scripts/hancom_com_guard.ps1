Set-StrictMode -Version Latest

$script:HancomSecurityModuleName = 'FilePathCheckerModuleExample'

function New-HancomGuardedObject {
    [CmdletBinding()]
    param(
        [switch]$Hidden,
        [Nullable[int]]$MessageBoxMode = $null
    )

    $hwp = $null
    try {
        $hwp = New-Object -ComObject HWPFrame.HwpObject
        $registered = $hwp.RegisterModule(
            'FilePathCheckDLL',
            $script:HancomSecurityModuleName
        )
        if (-not $registered) {
            throw "Hancom file-path security module registration failed: $script:HancomSecurityModuleName"
        }

        if ($Hidden) {
            try { $hwp.XHwpWindows.Item(0).Visible = $false } catch {}
        }
        if ($null -ne $MessageBoxMode) {
            [void]$hwp.SetMessageBoxMode($MessageBoxMode)
        }

        Write-Output -NoEnumerate $hwp
    }
    catch {
        if ($null -ne $hwp) {
            try { $hwp.Quit() } catch {}
            try {
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($hwp)
            }
            catch {}
        }
        throw
    }
}

function Close-HancomGuardedObject {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]$Hwp
    )

    try { [void]$Hwp.SetMessageBoxMode(0xFFFFFF) } catch {}
    try { $Hwp.Quit() } catch {}
    try {
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($Hwp)
    }
    catch {}
}
