# Docker can be a little precious sometimes
# https://lmonkiewicz.com/programming/get-noticed-2017/docker-problems-on-windows/
Param(
    [Parameter(Mandatory=$true)] $psycheVolume,
    [Parameter(Mandatory=$true)] $dockerImage
)

$psycheVolume = Resolve-Path $psycheVolume | Select-Object -ExpandProperty Path
$origMsysNoPathconv = $env:MSYS_NO_PATHCONV
$env:MSYS_NO_PATHCONV = 1
try {
    docker run -v ${psycheVolume}:/psyche -it $dockerImage
} finally {
    $env:MSYS_NO_PATHCONV = $origMsysNoPathconv
}
