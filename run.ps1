# Docker can be a little precious sometimes
# https://lmonkiewicz.com/programming/get-noticed-2017/docker-problems-on-windows/
Param(
    [Parameter(Mandatory=$true)] $dockerImage,
    $psycheVolume
)
$origMsysNoPathconv = $env:MSYS_NO_PATHCONV
$env:MSYS_NO_PATHCONV = 1
try {
    if ($psycheVolume) {
        $psycheVolume = Resolve-Path $psycheVolume | Select-Object -ExpandProperty Path
        docker run --rm -v "${psycheVolume}:/psyche:rw" -it "$dockerImage"
    } else {
        docker run --rm -it "$dockerImage"
    }
} finally {
    $env:MSYS_NO_PATHCONV = $origMsysNoPathconv
}
