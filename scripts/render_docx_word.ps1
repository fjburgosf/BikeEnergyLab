param([string]$Directory = 'docs/docx', [string]$Filter = '*.docx')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskDocs = (Resolve-Path -LiteralPath (Join-Path $taskRoot $Directory)).Path
if (-not $taskDocs.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar)) {
    throw 'Only task-owned DOCX files may be rendered.'
}
$taskQA = Join-Path $taskRoot 'build/docx-qa'
New-Item -ItemType Directory -Path $taskQA -Force | Out-Null
$taskWord = $null
try {
    $taskWord = New-Object -ComObject Word.Application
    $taskWord.Visible = $false
    $taskWord.DisplayAlerts = 0
    $taskWord.AutomationSecurity = 3
    foreach ($taskFile in Get-ChildItem -LiteralPath $taskDocs -Filter $Filter) {
        if ($taskFile.Extension -ne '.docx') { throw 'Only DOCX files may be rendered.' }
        $taskDocument = $null
        try {
            $taskDocument = $taskWord.Documents.Open($taskFile.FullName, $false, $false)
            $taskDocument.Fields.Update() | Out-Null
            $taskDocument.Repaginate()
            foreach ($taskTOC in $taskDocument.TablesOfContents) {
                $taskTOC.Update()
                if ($taskFile.BaseName -like 'Manual_*') {
                    $taskTOC.Range.ParagraphFormat.SpaceBefore = 0
                    $taskTOC.Range.ParagraphFormat.SpaceAfter = 0
                    $taskTOC.Range.ParagraphFormat.LineSpacingRule = 0
                }
                $taskTOC.UpdatePageNumbers()
            }
            $taskDocument.Repaginate()
            foreach ($taskSection in $taskDocument.Sections) {
                foreach ($taskFooter in $taskSection.Footers) {
                    $taskFooter.Range.Fields.Update() | Out-Null
                }
            }
            $taskDocument.Save()
            $taskPDF = Join-Path $taskQA ($taskFile.BaseName + '.pdf')
            $taskDocument.ExportAsFixedFormat($taskPDF, 17)
            $taskPages = $taskDocument.ComputeStatistics(2)
            Write-Output "$($taskFile.Name): $taskPages pages; native Word PDF $taskPDF"
        } finally {
            if ($null -ne $taskDocument) {
                $taskDocument.Close(0)
                [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskDocument) | Out-Null
            }
        }
    }
} finally {
    if ($null -ne $taskWord) {
        $taskWord.Quit()
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskWord) | Out-Null
    }
}
