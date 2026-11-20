param(
    [string]$mode = "ai",
    [int]$episodes = 3,
    [string]$renderer = "3d",
    [string]$theme = "spaceport",
    [double]$speed = 0.5,
    [string]$storm_severity = "moderate",
    [Nullable[double]]$wind = $null,
    [Nullable[double]]$turbulence = $null,
    [string]$policy_mode = "deterministic",
    [switch]$stochastic,
    [Nullable[int]]$seed = $null,
    [switch]$random_seeds
)

$repoRoot = $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

$cliArgs = @(
    (Join-Path $repoRoot "scripts\play_demo.py"),
    "--mode", $mode,
    "--episodes", $episodes,
    "--renderer", $renderer,
    "--theme", $theme,
    "--speed", $speed,
    "--storm-severity", $storm_severity,
    "--policy-mode", $policy_mode
)

if ($stochastic) {
    $cliArgs += @("--stochastic")
}
if ($seed -ne $null) {
    $cliArgs += @("--seed", $seed)
}
if ($random_seeds) {
    $cliArgs += @("--random-seeds")
}
if ($wind -ne $null) {
    $cliArgs += @("--wind", $wind)
}
if ($turbulence -ne $null) {
    $cliArgs += @("--turbulence", $turbulence)
}

if (Test-Path $venvPython) {
    & $venvPython @cliArgs
} else {
    python @cliArgs
}
