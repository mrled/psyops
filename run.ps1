# Docker can be a little precious sometimes
# https://lmonkiewicz.com/programming/get-noticed-2017/docker-problems-on-windows/
Param(
    [Parameter(Mandatory=$true)] $dockerImage,
    $psycheVolume
)

if ($psycheVolume) {
    $psycheVolume = Resolve-Path $psycheVolume | Select-Object -ExpandProperty Path
    $psycheVolumeArg = "-v ${psycheVolume}:/psyche"
}
$origMsysNoPathconv = $env:MSYS_NO_PATHCONV
$env:MSYS_NO_PATHCONV = 1
try {
    docker run --rm $psycheVolumeArg -it $dockerImage
} finally {
    $env:MSYS_NO_PATHCONV = $origMsysNoPathconv
}
