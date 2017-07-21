# Docker can be a little precious sometimes
# https://lmonkiewicz.com/programming/get-noticed-2017/docker-problems-on-windows/
Param(
    [Parameter(Mandatory=$true)] $dockerImage
)
$origMsysNoPathconv = $env:MSYS_NO_PATHCONV
$env:MSYS_NO_PATHCONV = 1
try {
    docker run --rm -v "${PSScriptRoot}:/psyops:rw" -it "$dockerImage"
} finally {
    $env:MSYS_NO_PATHCONV = $origMsysNoPathconv
}
